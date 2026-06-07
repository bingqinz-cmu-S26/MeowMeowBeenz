#!/usr/bin/env python3
import json
import os
import re
import base64
import hashlib
import hmac
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MINIMAX_DEFAULT_URL = "https://api.minimax.io/v1/chat/completions"
MINIMAX_DEFAULT_MODEL = "M2-her"
MINIMAX_TIMEOUT_SECONDS = 12


class AppHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/agent":
            self.handle_agent()
            return
        if self.path == "/api/livekit-token":
            self.handle_livekit_token()
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
