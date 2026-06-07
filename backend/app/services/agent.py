import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.services.health_rules import build_range_report


def answer_owner_question(question: str, timeline: list[dict], report: dict) -> str:
    normalized = question.strip().lower()
    if not timeline:
        return (
            "I do not have any observations yet. Start a live analysis or add a demo event, "
            "then I can summarize state, vocalization, activity, appetite, and litter signals."
        )
    if any(term in normalized for term in ("worry", "concern", "vet", "health", "sick", "bad")):
        return build_concern_answer(report)
    if any(term in normalized for term in ("meow", "yowl", "vocal", "sound", "cry")):
        return build_vocal_answer(timeline)
    return build_daily_answer(timeline, report)


def build_concern_answer(report: dict) -> str:
    alerts = report.get("alerts", [])
    if not alerts:
        return (
            "Based on the timeline, I do not see a warning signal yet. This is still a limited observation window, "
            "so keep building the baseline and watch appetite, litter behavior, and activity."
        )
    top = alerts[0]
    return (
        f"I would mark today as {report.get('overall', 'normal')}. "
        f'The strongest signal is "{top["title"]}" because {top["evidence"][0]} '
        f"This is not a diagnosis; it is a behavior change worth monitoring. {top['suggestion']}"
    )


def build_vocal_answer(timeline: list[dict]) -> str:
    vocal_events = [
        event
        for event in timeline
        if any(token in event.get("soundType", "") for token in ("meow", "yowl", "caterwaul", "chirp"))
    ]
    if not vocal_events:
        return (
            "I do not see a vocalization event in the current timeline. If you heard one, run a live analysis "
            "during the sound so I can ground the answer in a clip."
        )
    latest = vocal_events[-1]
    confidence = int(float(latest.get("confidence", 0)) * 100)
    return (
        f'The latest vocal event was "{latest.get("soundType", "")}" with {confidence}% confidence. '
        f'The model interpreted it as {latest.get("intent", "")}. Evidence: {latest.get("summary", "")} '
        "I would check simple needs first and keep watching if it repeats."
    )


def build_daily_answer(timeline: list[dict], report: dict) -> str:
    latest = timeline[-1]
    confidence = int(float(latest.get("confidence", 0)) * 100)
    return (
        f"Today I have {report.get('totalEvents', 0)} observations. Overall status is {report.get('overall', 'normal')}. "
        f"Latest state: {latest.get('state', '')}, interpreted as {latest.get('intent', '')} with {confidence}% confidence. "
        f"{report.get('summary', '')}"
    )


def call_minimax(question: str, timeline: list[dict], report: dict) -> str:
    if not settings.minimax_api_key:
        raise ValueError("MINIMAX_API_KEY is not set.")

    body = {
        "model": settings.minimax_model,
        "messages": build_messages(question, timeline[-10:], report),
        "temperature": 0.2,
        "max_tokens": 260,
        "stream": False,
    }
    request = Request(
        settings.minimax_api_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.minimax_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiniMax returned HTTP {error.code}: {detail[:500]}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach MiniMax: {error.reason}") from error

    try:
        return clean_model_text(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("MiniMax response did not include choices[0].message.content.") from error


def build_messages(question: str, timeline: list[dict], report: dict) -> list[dict]:
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


def clean_model_text(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", str(text), flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return cleaned.strip()


def friendly_time(raw_timestamp: str | datetime | None, now: datetime | None = None) -> str:
    """Render a readable relative time label for voice retrieval responses."""
    if raw_timestamp is None:
        return "recently"

    event_time = _parse_datetime(raw_timestamp)
    if event_time is None:
        return "recently"

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    delta = current - event_time
    if delta.total_seconds() < 0:
        delta = -delta
        suffix = "from now"
    else:
        suffix = "ago"

    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 1:
        return f"just now"
    if total_minutes < 60:
        return f"{total_minutes} minute{'s' if total_minutes != 1 else ''} {suffix}"

    total_hours = int(total_minutes // 60)
    if total_hours < 24:
        return f"{total_hours} hour{'s' if total_hours != 1 else ''} {suffix}"

    total_days = int(total_hours // 24)
    if total_days < 7:
        return f"{total_days} day{'s' if total_days != 1 else ''} {suffix}"
    return event_time.strftime("%b %d")


def _parse_datetime(raw_timestamp: str | datetime) -> datetime | None:
    if isinstance(raw_timestamp, datetime):
        return raw_timestamp.astimezone(timezone.utc)
    if not isinstance(raw_timestamp, str) or not raw_timestamp.strip():
        return None
    normalized = raw_timestamp.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def ask_agent(question: str, timeline: list[dict], report: dict | None = None) -> dict:
    report_data = report or build_range_report(timeline, "day")
    try:
        answer = call_minimax(question, timeline, report_data)
        return {"provider": "minimax", "text": answer}
    except Exception:
        return {
            "provider": "local",
            "text": (
                f"{answer_owner_question(question, timeline, report_data)}\n\n"
                "MiniMax is taking too long, so Beenz used the local timeline summary."
            ),
        }
