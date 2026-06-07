import base64
import json
import random
import re
from collections.abc import Mapping
from datetime import datetime, timezone
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.services.sample_data import SCENARIO_CATALOG, create_scenario_event


GEMINI_PROMPT = (
    "You are a cat-observation assistant. Analyze this uploaded clip and return JSON only. "
    "Do not use markdown fences or extra text. Required keys: summary, state, intent, "
    "behaviorLabel, soundType, confidence, riskLevel, signals, suggestion. "
    "Use 0.0-1.0 for confidence. riskLevel must be one of: normal, watch, review. "
    "If the cat appears relaxed, purring, content, playful, or affectionate, use riskLevel normal. "
    "If uncertain, lower confidence and avoid diagnosis."
)


def _local_analysis_payload(filename: str, size: int) -> dict:
    scenario = random.choice(list(SCENARIO_CATALOG.keys()))
    event = create_scenario_event(scenario)
    return {
        "ok": True,
        "provider": "local",
        "text": (
            f"Analyzed {filename} ({size} bytes) locally. "
            f"Gemini hook unavailable or key missing."
        ),
        "event": event,
    }


def _merge_with_model_output(event: dict, model_output: Mapping[str, object]) -> None:
    for key in (
        "state",
        "intent",
        "behaviorLabel",
        "soundType",
        "summary",
        "suggestion",
    ):
        value = model_output.get(key)
        if isinstance(value, str) and value.strip():
            event[key] = value.strip()

    confidence = model_output.get("confidence")
    if isinstance(confidence, int | float):
        event["confidence"] = max(0.0, min(1.0, float(confidence)))

    risk_level = model_output.get("riskLevel")
    if isinstance(risk_level, str) and risk_level in {"normal", "watch", "review"}:
        event["riskLevel"] = risk_level

    signals = model_output.get("signals")
    if isinstance(signals, list):
        filtered: list[str] = []
        for token in signals:
            if isinstance(token, str):
                stripped = token.strip()
                if stripped:
                    filtered.append(stripped)
        event["signals"] = filtered


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\s*```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    return cleaned.strip()


def _coerce_json(text: str) -> dict | None:
    text = _strip_code_fences(text)
    if not text:
        return None

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, Mapping):
        return dict(parsed)
    return None


def _coerce_model_output(text: str) -> dict:
    parsed = _coerce_json(text)
    if parsed:
        return parsed

    # Salvage common JSON-ish model output, including truncated/debug strings.
    found: dict[str, object] = {}
    for match in re.finditer(r'"([^"]+)"\s*:\s*"((?:\\.|[^"\\])*)"', text, flags=re.DOTALL):
        key, value = match.groups()
        try:
            found[key] = json.loads(f'"{value}"')
        except json.JSONDecodeError:
            found[key] = value

    confidence_match = re.search(r'"confidence"\s*:\s*([0-9]*\.?[0-9]+)', text)
    if confidence_match:
        found["confidence"] = float(confidence_match.group(1))

    risk_match = re.search(r'"riskLevel"\s*:\s*"([^"]+)"', text)
    if risk_match:
        found["riskLevel"] = risk_match.group(1)

    return found


def _first_string(data: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _confidence(value: object) -> float:
    if isinstance(value, int | float):
        score = float(value)
    elif isinstance(value, str):
        stripped = value.strip().rstrip("%")
        try:
            score = float(stripped)
            if "%" in value or score > 1:
                score /= 100
        except ValueError:
            score = 0.6
    else:
        score = 0.6
    return max(0.0, min(1.0, score))


def _risk_level(value: object, model_output: Mapping[str, object]) -> str:
    raw = str(value or "").strip().lower()
    text = " ".join(str(model_output.get(key, "")) for key in ("summary", "state", "intent", "behaviorLabel", "soundType"))
    text = text.lower()

    if raw in {"normal", "watch", "review"}:
        return raw
    if raw in {"low", "none", "safe", "ok", "okay", "happy", "content", "relaxed"}:
        return "normal"
    if raw in {"medium", "moderate", "caution", "monitor"}:
        return "watch"
    if raw in {"high", "alert", "urgent", "concern"}:
        return "review"
    if any(token in text for token in ("distress", "pain", "discomfort", "yowl", "hiss", "growl")):
        return "watch"
    return "normal"


def _signals(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]
    return []


def _event_from_model_output(model_output: Mapping[str, object], raw_text: str, filename: str) -> dict:
    summary = _first_string(model_output, "summary", "text", "description")
    has_structured_fields = any(
        _first_string(model_output, key)
        for key in ("state", "intent", "behaviorLabel", "soundType")
    )
    if not summary:
        summary = _strip_code_fences(raw_text) or f"Gemini analyzed {filename}, but did not return a structured summary."
    elif not has_structured_fields:
        summary = "Gemini returned an incomplete structured response. Open the raw response to inspect the model output."

    state = _first_string(model_output, "state", "mood", "status") or "Incomplete Gemini response"
    intent = _first_string(model_output, "intent", "likelyIntent") or "unknown"
    behavior = _first_string(model_output, "behaviorLabel", "behavior", "behavior_label", "activity") or "unknown"
    sound = _first_string(model_output, "soundType", "sound", "sound_type", "audio", "vocalization") or "unknown"
    suggestion = _first_string(model_output, "suggestion", "recommendation", "nextStep")
    if not suggestion:
        suggestion = "Treat this as an observation, and compare it with the cat's recent baseline."

    return {
        "id": f"evt_gemini_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{secrets.token_hex(3)}",
        "time": datetime.now(timezone.utc).isoformat(),
        "source": "gemini",
        "state": state,
        "intent": intent,
        "behaviorLabel": behavior,
        "soundType": sound,
        "confidence": _confidence(model_output.get("confidence")),
        "riskLevel": _risk_level(model_output.get("riskLevel"), model_output),
        "signals": _signals(model_output.get("signals")),
        "summary": summary,
        "suggestion": suggestion,
    }


def _analyze_with_gemini(file_data: bytes, mime_type: str) -> dict:
    if not settings.gemini_api_key:
        return {"provider": "local", "text": "Gemini API key is missing."}

    max_bytes_for_upload = 6 * 1024 * 1024
    if len(file_data) > max_bytes_for_upload:
        return {"provider": "local", "text": "Clip is too large for Gemini upload (max 6MB)."}

    url = (
        f"{settings.gemini_api_url.format(model=settings.gemini_model)}"
        f"?key={settings.gemini_api_key}"
    )
    body = {
        "contents": [
            {
                "parts": [
                    {"text": GEMINI_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(file_data).decode("utf-8"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
        },
    }

    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini request failed ({exc.code}): {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Gemini: {exc}") from exc

    try:
        text = str(payload["candidates"][0]["content"]["parts"][0]["text"]).strip()
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini returned a malformed response.")

    parsed = _coerce_model_output(text)
    if not parsed:
        return {"provider": "gemini", "text": text, "rawText": text, "parsed": {}}

    result = {"provider": "gemini", "rawText": text, "parsed": parsed}
    result.update(parsed)
    return result


def analyze_video_clip(filename: str, file_data: bytes, mime_type: str) -> dict:
    filename = filename or "upload.mov"

    try:
        model_result = _analyze_with_gemini(file_data=file_data, mime_type=mime_type)
    except Exception as exc:  # noqa: BLE001
        summary = _local_analysis_payload(filename=filename, size=len(file_data))
        summary["text"] = f"{summary['text']} Fallback used: {str(exc)[:220]}"
        summary["rawText"] = summary["text"]
        return summary

    if model_result.get("provider") != "gemini":
        summary = _local_analysis_payload(filename=filename, size=len(file_data))
        summary["text"] = str(model_result.get("text") or summary["text"])
        summary["rawText"] = summary["text"]
        return summary

    text = model_result.get("summary")
    raw_text = str(model_result.get("rawText") or model_result.get("text") or "").strip()
    if not isinstance(text, str) or not text.strip():
        text = raw_text

    model_fields = model_result.get("parsed")
    if not isinstance(model_fields, Mapping):
        model_fields = model_result
    event = _event_from_model_output(model_fields, raw_text=raw_text, filename=filename)
    _merge_with_model_output(event=event, model_output=model_fields)

    return {
        "ok": True,
        "provider": "gemini",
        "text": str(text).strip() or event["summary"],
        "rawText": raw_text or str(text).strip(),
        "event": event,
    }
