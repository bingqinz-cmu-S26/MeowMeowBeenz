#!/usr/bin/env python3
import json
import os
import re
import base64
import cgi
import hashlib
import hmac
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


MINIMAX_DEFAULT_URL = "https://api.minimax.io/v1/chat/completions"
MINIMAX_DEFAULT_MODEL = "M2-her"
MINIMAX_TIMEOUT_SECONDS = 12
CAT_MODEL_TIMEOUT_SECONDS = 45
GEMINI_DEFAULT_BASE = "https://generativelanguage.googleapis.com"
GEMINI_DEFAULT_MODEL = "gemini-3.5-flash"
GEMINI_TIMEOUT_SECONDS = 60
GEMINI_INLINE_LIMIT_BYTES = 12 * 1024 * 1024
MAX_CLIP_BYTES = 80 * 1024 * 1024


class AppHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/agent":
            self.handle_agent()
            return
        if self.path == "/api/livekit-token":
            self.handle_livekit_token()
            return
        if self.path == "/api/analyze-clip":
            self.handle_analyze_clip()
            return

        self.send_json({"ok": False, "error": "Not found"}, status=404)

    def handle_agent(self):
        try:
            payload = self.read_json()
            answer = call_minimax(payload)
            self.send_json({"ok": True, "answer": answer, "provider": "minimax"})
        except MissingKeyError as error:
            self.send_json({"ok": False, "error": str(error)}, status=503)
        except BadRequestError as error:
            self.send_json({"ok": False, "error": str(error)}, status=400)
        except UpstreamError as error:
            self.send_json({"ok": False, "error": str(error)}, status=502)

    def handle_analyze_clip(self):
        try:
            clip = self.read_clip_upload()
            result = analyze_clip(clip)
            self.send_json({"ok": True, **result})
        except BadRequestError as error:
            self.send_json({"ok": False, "error": str(error)}, status=400)
        except UpstreamError as error:
            self.send_json({"ok": False, "error": str(error)}, status=502)

    def handle_livekit_token(self):
        try:
            payload = self.read_json()
            token_payload = create_livekit_token(payload)
            self.send_json({"ok": True, **token_payload})
        except MissingLiveKitConfigError as error:
            self.send_json({"ok": False, "configured": False, "error": str(error)}, status=503)
        except BadRequestError as error:
            self.send_json({"ok": False, "error": str(error)}, status=400)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 1_000_000:
            raise BadRequestError("Request body is empty or too large.")

        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise BadRequestError("Request body must be valid JSON.") from error

    def read_clip_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            raise BadRequestError("Clip analysis expects multipart/form-data.")

        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise BadRequestError("Clip upload is empty.")
        if length > MAX_CLIP_BYTES:
            raise BadRequestError("Clip is too large. Use a file under 80 MB for this MVP.")

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(length),
            },
        )
        if "clip" not in form:
            raise BadRequestError("Missing clip file.")

        clip_field = form["clip"]
        if isinstance(clip_field, list):
            clip_field = clip_field[0]
        filename = sanitize_filename(clip_field.filename or "uploaded-clip")
        data = clip_field.file.read()
        clip_type = clip_field.type or "application/octet-stream"
        if not data:
            raise BadRequestError("Clip file is empty.")
        if not is_supported_clip(filename, clip_type):
            raise BadRequestError("Upload an audio or video clip.")

        return {
            "filename": filename,
            "content_type": clip_type,
            "data": data,
            "size": len(data),
        }

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MissingKeyError(Exception):
    pass


class BadRequestError(Exception):
    pass


class UpstreamError(Exception):
    pass


class MissingLiveKitConfigError(Exception):
    pass


def create_livekit_token(payload):
    livekit_url = os.environ.get("LIVEKIT_URL")
    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")
    if not livekit_url or not api_key or not api_secret:
        raise MissingLiveKitConfigError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are required.")

    room = safe_token_value(payload.get("room") or "mochi-monitor-demo", "room")
    identity = safe_token_value(payload.get("identity") or f"owner-{int(time.time())}", "identity")
    now = int(time.time())
    claims = {
        "iss": api_key,
        "sub": identity,
        "nbf": now - 10,
        "exp": now + 60 * 60,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }
    return {
        "configured": True,
        "url": livekit_url,
        "room": room,
        "identity": identity,
        "token": sign_jwt(claims, api_secret),
    }


def safe_token_value(value, field_name):
    text = str(value).strip()
    if not text or len(text) > 80:
        raise BadRequestError(f"{field_name} must be 1-80 characters.")
    if not re.match(r"^[A-Za-z0-9_.:-]+$", text):
        raise BadRequestError(f"{field_name} may only contain letters, numbers, dash, underscore, dot, or colon.")
    return text


def sign_jwt(claims, secret):
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{b64url_json(header)}.{b64url_json(claims)}"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def b64url_json(value):
    return b64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def b64url(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def is_supported_clip(filename, content_type):
    lowered = filename.lower()
    if content_type.startswith("video/") or content_type.startswith("audio/"):
        return True
    return lowered.endswith((".mp4", ".mov", ".webm", ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".ogg"))


def sanitize_filename(filename):
    basename = os.path.basename(str(filename)).strip() or "uploaded-clip"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", basename).strip(".-")
    return sanitized[:120] or "uploaded-clip"


def analyze_clip(clip):
    if os.environ.get("GEMINI_API_KEY"):
        return call_gemini_clip(clip)

    model_url = os.environ.get("CAT_MODEL_URL")
    if model_url:
        return call_cat_model(model_url, clip)
    return local_clip_analysis(clip)


def call_gemini_clip(clip):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise MissingKeyError("GEMINI_API_KEY is required for Gemini clip analysis.")

    model = os.environ.get("GEMINI_MODEL", GEMINI_DEFAULT_MODEL)
    media_part = gemini_media_part(api_key, clip)
    request_body = {
        "contents": [{
            "role": "user",
            "parts": [
                media_part,
                {"text": build_gemini_clip_prompt()},
            ],
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 1200,
            "responseMimeType": "application/json",
            "responseSchema": gemini_event_schema(),
        },
    }
    generate_url = f"{gemini_base_url()}/v1beta/models/{quote(model, safe='')}:generateContent"
    try:
        data = post_gemini_json(generate_url, api_key, request_body, timeout=GEMINI_TIMEOUT_SECONDS)
    except UpstreamError as error:
        if "response" not in str(error).lower():
            raise
        request_body["generationConfig"].pop("responseMimeType", None)
        request_body["generationConfig"].pop("responseSchema", None)
        data = post_gemini_json(generate_url, api_key, request_body, timeout=GEMINI_TIMEOUT_SECONDS)
    text = gemini_response_text(data)
    payload = parse_json_object_text(text)
    payload["provider"] = f"gemini:{model}"
    return normalize_clip_model_response(payload, clip, payload["provider"])


def gemini_media_part(api_key, clip):
    if clip["size"] <= int(os.environ.get("GEMINI_INLINE_LIMIT_BYTES", GEMINI_INLINE_LIMIT_BYTES)):
        return {
            "inline_data": {
                "mime_type": clip["content_type"],
                "data": base64.b64encode(clip["data"]).decode("ascii"),
            }
        }

    file_data = upload_gemini_file(api_key, clip)
    return {
        "file_data": {
            "mime_type": clip["content_type"],
            "file_uri": file_data["uri"],
        }
    }


def upload_gemini_file(api_key, clip):
    upload_start = Request(
        f"{gemini_base_url()}/upload/v1beta/files",
        data=json.dumps({"file": {"display_name": clip["filename"]}}).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(clip["size"]),
            "X-Goog-Upload-Header-Content-Type": clip["content_type"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(upload_start, timeout=GEMINI_TIMEOUT_SECONDS) as response:
            upload_url = response.headers.get("x-goog-upload-url")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise UpstreamError(f"Gemini file upload start failed HTTP {error.code}: {detail[:500]}") from error
    except URLError as error:
        raise UpstreamError(f"Could not start Gemini file upload: {error.reason}") from error

    if not upload_url:
        raise UpstreamError("Gemini did not return a resumable upload URL.")

    upload_finalize = Request(
        upload_url,
        data=clip["data"],
        headers={
            "Content-Length": str(clip["size"]),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        },
        method="POST",
    )
    try:
        with urlopen(upload_finalize, timeout=GEMINI_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise UpstreamError(f"Gemini file upload failed HTTP {error.code}: {detail[:500]}") from error
    except URLError as error:
        raise UpstreamError(f"Could not upload clip to Gemini: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise UpstreamError("Gemini file upload returned invalid JSON.") from error

    file_info = payload.get("file") or {}
    if not file_info.get("uri"):
        raise UpstreamError("Gemini file upload did not return file.uri.")
    wait_for_gemini_file(api_key, file_info)
    return file_info


def wait_for_gemini_file(api_key, file_info):
    name = file_info.get("name")
    state = (file_info.get("state") or "").upper()
    if not name or state in {"", "ACTIVE"}:
        return

    for _ in range(10):
        time.sleep(1)
        request = Request(
            f"{gemini_base_url()}/v1beta/{quote(name, safe='/')}",
            headers={"x-goog-api-key": api_key},
            method="GET",
        )
        try:
            with urlopen(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
                refreshed = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, json.JSONDecodeError):
            return
        state = (refreshed.get("state") or "").upper()
        if state == "ACTIVE":
            return
        if state == "FAILED":
            raise UpstreamError("Gemini file processing failed.")


def post_gemini_json(url, api_key, body, timeout):
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise UpstreamError(f"Gemini returned HTTP {error.code}: {detail[:500]}") from error
    except URLError as error:
        raise UpstreamError(f"Could not reach Gemini: {error.reason}") from error
    except TimeoutError as error:
        raise UpstreamError("Gemini request timed out.") from error
    except json.JSONDecodeError as error:
        raise UpstreamError("Gemini returned invalid JSON.") from error


def gemini_base_url():
    return os.environ.get("GEMINI_API_BASE", GEMINI_DEFAULT_BASE).rstrip("/")


def build_gemini_clip_prompt():
    return (
        "Analyze this uploaded cat audio/video clip for MeowMeowBeenz. "
        "Return only one compact JSON object. Do not include markdown, code fences, prose, or reasoning. "
        "The JSON object must contain: text, state, intent, behaviorLabel, soundType, confidence, "
        "riskLevel, signals, summary, suggestion. "
        "Use the same field semantics as the app mock events: state is a short human-readable status; "
        "intent is the likely cat intent; behaviorLabel is a compact behavior token such as "
        "maintenance_nutrition.eating, inactive_lying.resting, active_walking, active_playfight.playing, "
        "maintenance_littering.digging, maintenance_scratching, or unknown; soundType is a compact audio token "
        "such as quiet, short_meow, repeated_meow, chirp, caterwauling, distress_like_yowl, or unknown. "
        "riskLevel must be normal, watch, or review. Do not diagnose disease. "
        "If the clip is ambiguous, keep riskLevel normal or watch unless there is a clear reason to review."
    )


def gemini_event_schema():
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "state": {"type": "string"},
            "intent": {"type": "string"},
            "behaviorLabel": {"type": "string"},
            "soundType": {"type": "string"},
            "confidence": {"type": "number"},
            "riskLevel": {"type": "string", "enum": ["normal", "watch", "review"]},
            "signals": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
            "suggestion": {"type": "string"},
        },
        "required": [
            "text",
            "state",
            "intent",
            "behaviorLabel",
            "soundType",
            "confidence",
            "riskLevel",
            "signals",
            "summary",
            "suggestion",
        ],
    }


def gemini_response_text(data):
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError) as error:
        raise UpstreamError("Gemini response did not include candidates[0].content.parts.") from error
    text_parts = [str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("text")]
    text = "".join(text_parts).strip()
    if not text:
        raise UpstreamError("Gemini response did not include text.")
    return text


def parse_json_object_text(text):
    clean = str(text).strip()
    clean = re.sub(r"^```(?:json)?", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"```$", "", clean).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
        if not match:
            raise UpstreamError("Gemini did not return JSON in the expected event format.")
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise UpstreamError("Gemini returned malformed JSON.") from error


def call_cat_model(model_url, clip):
    field_name = os.environ.get("CAT_MODEL_FILE_FIELD", "clip")
    body, content_type = encode_multipart(
        fields={
            "mode": "clip_analysis",
            "product": "MeowMeowBeenz",
        },
        files={
            field_name: clip,
        },
    )
    headers = {
        "Accept": "application/json, text/plain",
        "Content-Type": content_type,
    }
    api_key = os.environ.get("CAT_MODEL_API_KEY")
    if api_key:
        headers[os.environ.get("CAT_MODEL_AUTH_HEADER", "Authorization")] = f"Bearer {api_key}"

    request = Request(model_url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=CAT_MODEL_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8", errors="replace")
            response_type = response.headers.get("Content-Type", "")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise UpstreamError(f"Cat model returned HTTP {error.code}: {detail[:500]}") from error
    except URLError as error:
        raise UpstreamError(f"Could not reach cat model: {error.reason}") from error
    except TimeoutError as error:
        raise UpstreamError("Cat model request timed out.") from error

    if "application/json" in response_type:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise UpstreamError("Cat model returned invalid JSON.") from error
    else:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"text": raw}
    return normalize_clip_model_response(payload, clip, "cat-model")


def encode_multipart(fields, files):
    boundary = f"----meowmeowbeenz{int(time.time() * 1000)}"
    chunks = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
            f"{value}\r\n".encode("utf-8"),
        ])
    for name, clip in files.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{clip["filename"]}"\r\n'
            ).encode("utf-8"),
            f'Content-Type: {clip["content_type"]}\r\n\r\n'.encode("utf-8"),
            clip["data"],
            b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def normalize_clip_model_response(payload, clip, fallback_provider):
    if not isinstance(payload, dict):
        payload = {"text": str(payload)}

    text = first_text(payload, ["text", "response", "message", "summary", "description"])
    event_source = payload.get("event") or payload.get("analysis") or payload
    if not isinstance(event_source, dict):
        event_source = {}

    summary = first_text(event_source, ["summary", "text", "response"]) or text
    event = {
        "source": "uploaded_clip_analysis",
        "state": first_text(event_source, ["state", "status"]) or "Clip analyzed",
        "intent": compact_token(first_text(event_source, ["intent", "predicted_intent"])) or "unknown",
        "behaviorLabel": compact_token(first_text(event_source, ["behaviorLabel", "behavior", "behavior_label"])) or "unknown",
        "soundType": compact_token(first_text(event_source, ["soundType", "sound", "sound_type", "audio"])) or "unknown",
        "confidence": safe_confidence(event_source.get("confidence", payload.get("confidence", 0))),
        "riskLevel": safe_risk(event_source.get("riskLevel", event_source.get("risk", payload.get("riskLevel", "normal")))),
        "signals": safe_signals(event_source.get("signals", payload.get("signals", []))),
        "summary": summary or "The model analyzed this uploaded clip.",
        "suggestion": first_text(event_source, ["suggestion", "recommendation"]) or "Use this clip-level result as a preview; timeline context will come from LiveKit later.",
    }
    return {
        "provider": payload.get("provider") or fallback_provider,
        "text": text or event["summary"],
        "event": event,
        "file": {
            "name": clip["filename"],
            "type": clip["content_type"],
            "size": clip["size"],
        },
    }


def local_clip_analysis(clip):
    text = (
        "Local demo analysis: clip upload succeeded. "
        "Gemini is not configured yet, so this is a placeholder event in the app mock-data format."
    )
    payload = {
        "provider": "local-demo",
        "text": text,
        "analysis": {
            "state": "Clip ready for model",
            "intent": "pending_model_prediction",
            "behavior": "unknown",
            "sound": "unknown",
            "confidence": 0.0,
            "riskLevel": "normal",
            "summary": text,
            "suggestion": "Set GEMINI_API_KEY on the server to send uploaded clips to Gemini 3.5 Flash.",
        },
    }
    return normalize_clip_model_response(payload, clip, "local-demo")


def first_text(source, keys):
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def compact_token(value):
    token = str(value or "").strip().lower()
    token = re.sub(r"[^a-z0-9.]+", "_", token)
    token = re.sub(r"_+", "_", token).strip("_.")
    return token


def safe_confidence(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if number > 1:
        number = number / 100
    return max(0, min(1, number))


def safe_risk(value):
    normalized = str(value or "normal").lower().strip()
    if normalized in {"review", "alert", "high"}:
        return "review"
    if normalized in {"watch", "medium", "warning"}:
        return "watch"
    return "normal"


def safe_signals(value):
    if isinstance(value, list):
        return [compact_token(item) for item in value if compact_token(item)][:8]
    if isinstance(value, str) and value.strip():
        return [compact_token(value)]
    return []


def call_minimax(payload):
    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        raise MissingKeyError("MINIMAX_API_KEY is not set. Falling back to local agent is recommended.")

    question = str(payload.get("question", "")).strip()
    if not question:
        raise BadRequestError("Question is required.")

    timeline = payload.get("timeline", [])
    report = payload.get("report", {})
    if not isinstance(timeline, list) or not isinstance(report, dict):
        raise BadRequestError("Timeline must be a list and report must be an object.")

    api_url = os.environ.get("MINIMAX_API_URL", MINIMAX_DEFAULT_URL)
    model = os.environ.get("MINIMAX_MODEL", MINIMAX_DEFAULT_MODEL)
    body = {
        "model": model,
        "messages": build_messages(question, timeline[-10:], report),
        "temperature": 0.2,
        "max_tokens": 260,
        "stream": False,
    }

    request = Request(
        api_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=MINIMAX_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise UpstreamError(f"MiniMax returned HTTP {error.code}: {detail[:500]}") from error
    except URLError as error:
        raise UpstreamError(f"Could not reach MiniMax: {error.reason}") from error
    except TimeoutError as error:
        raise UpstreamError("MiniMax request timed out.") from error

    try:
        return clean_model_text(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as error:
        raise UpstreamError("MiniMax response did not include choices[0].message.content.") from error


def build_messages(question, timeline, report):
    system = (
        "You are MeowMeowBeenz's cat wellness assistant. "
        "Answer directly using only the provided timeline and daily report. "
        "Do not deliberate, reason step-by-step, or explain your process. "
        "Start with the answer. "
        "You may discuss behavior, intent, routine changes, and monitoring suggestions. "
        "Never diagnose disease or claim certainty. "
        "Do not include hidden reasoning, chain-of-thought, XML tags, markdown tables, or emoji. "
        "If risk is non-trivial, recommend observation, checking food/water/litter, reviewing clips, or contacting a vet if patterns persist. "
        "Be concise, warm, and practical in 2-4 short sentences. Reply in the same language as the owner."
    )
    context = {
        "owner_question": question,
        "daily_report": report,
        "timeline_recent_first": list(reversed(timeline)),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]


def clean_model_text(text):
    cleaned = re.sub(r"<think>.*?</think>", "", str(text), flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return cleaned.strip()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "4173"))
    server = ThreadingHTTPServer(("", port), AppHandler)
    print(f"MeowMeowBeenz serving on http://localhost:{port}")
    print(f"MiniMax model: {os.environ.get('MINIMAX_MODEL', MINIMAX_DEFAULT_MODEL)}")
    server.serve_forever()
