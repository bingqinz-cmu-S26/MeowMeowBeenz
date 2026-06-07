import base64
import json
import random
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.services.sample_data import SCENARIO_CATALOG, create_scenario_event


GEMINI_PROMPT = (
    "You are a cat-observation assistant. Analyze this uploaded clip and return JSON only with keys "
    "summary, state, intent, behaviorLabel, soundType, confidence, riskLevel, signals, suggestion. "
    "Use 0.0-1.0 for confidence and include at least one concise summary sentence. "
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


def _coerce_json(text: str) -> dict | None:
    text = text.strip()
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
            "maxOutputTokens": 512,
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

    text = None
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Gemini returned a malformed response.")

    parsed = _coerce_json(str(text))
    summary = str(text).strip()
    if not parsed:
        return {"provider": "gemini", "text": summary}

    result = {"provider": "gemini", "summary": summary}
    result.update(parsed)
    return result


def analyze_video_clip(filename: str, file_data: bytes, mime_type: str) -> dict:
    summary = _local_analysis_payload(filename=filename or "upload.mov", size=len(file_data))

    try:
        model_result = _analyze_with_gemini(file_data=file_data, mime_type=mime_type)
    except Exception as exc:  # noqa: BLE001
        summary["text"] = f"{summary['text']} Fallback used: {str(exc)[:220]}"
        return summary

    text = model_result.get("summary")
    if isinstance(text, str) and text.strip():
        summary["text"] = text.strip()
    elif model_result.get("text"):
        summary["text"] = str(model_result["text"]).strip()

    merged = dict(summary["event"])
    _merge_with_model_output(event=merged, model_output=model_result)

    summary["event"] = dict(merged)
    summary["provider"] = str(model_result.get("provider", summary["provider"]))
    return summary
