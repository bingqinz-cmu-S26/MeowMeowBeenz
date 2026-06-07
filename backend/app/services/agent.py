import json
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.services.health_rules import build_range_report
from app.services.mock_store import get_public_cats

CAT_SPECIFIC_TERMS = {
    "meow", "meows", "yowl", "yowling", "vocal", "vocalization", "sound", "cry", "cried",
    "doing", "feeling", "mood", "ate", "eating", "food", "hungry", "litter", "sleep",
    "sleeping", "play", "playing", "groom", "grooming", "scratch", "scratching", "worry",
    "concern", "sick", "hurt", "pain", "stiff", "hiding", "restless",
}
SINGULAR_CAT_REFERENCES = {
    "cat", "kitty", "he", "him", "his", "she", "her", "hers", "they", "them", "their",
}
HOUSEHOLD_TERMS = {
    "cats", "everyone", "everybody", "all", "household", "both", "overall", "together",
}


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


def call_minimax(
    question: str,
    timeline: list[dict],
    report: dict,
    history: list[dict] | None = None,
    cat_context: dict | None = None,
) -> str:
    if not settings.minimax_api_key:
        raise ValueError("MINIMAX_API_KEY is not set.")

    body = {
        "model": settings.minimax_model,
        "messages": build_messages(question, timeline[-10:], report, history=history or [], cat_context=cat_context),
        "temperature": 0.2,
        "max_tokens": 140,
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


def build_messages(
    question: str,
    timeline: list[dict],
    report: dict,
    history: list[dict],
    cat_context: dict | None,
) -> list[dict]:
    system = (
        "You are MeowMeowBeenz's cat wellness assistant. "
        "Answer directly using only the provided cat profiles, timeline, daily report, and recent chat history. "
        "The backend has already resolved whether the owner means one cat or the whole household. "
        "If selected_cat_profile is present, answer profile questions such as age, birth date, and device from it. "
        "If selected_cat is present, answer behavior questions about that cat only. If selected_cat is null, answer about the household only. "
        "Do not deliberate, reason step-by-step, or explain your process. "
        "Answer exactly the owner's current question and then stop. Never invent follow-up User or AI turns. "
        "Start with the answer. "
        "You may discuss behavior, intent, routine changes, and monitoring suggestions. "
        "Never diagnose disease or claim certainty. "
        "Do not include hidden reasoning, chain-of-thought, XML tags, markdown tables, source lists, signatures, or emoji. "
        "Do not ask promotional follow-up questions like whether the owner wants human-year conversion. "
        "If risk is non-trivial, recommend observation, checking food/water/litter, reviewing clips, or contacting a vet if patterns persist. "
        "Be concise, warm, and practical in 2-4 short sentences. Reply in the same language as the owner."
    )
    context = {
        "owner_question": question,
        "selected_cat": cat_context,
        "selected_cat_profile": cat_context,
        "cat_profiles": cat_profiles_for_context(),
        "daily_report": report,
        "timeline_recent_first": list(reversed(timeline)),
        "recent_chat_history": history[-8:],
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]


def clean_model_text(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", str(text), flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.split(
        r"\n\s*(?:User|Owner|AI|Assistant|MeowMeowBeenz)\s*(?:\n|$)|"
        r"\n\s*\|.*\|.*\n|"
        r"\b(?:Would you like|Do you want|Please let me know)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
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


def ask_agent(
    question: str,
    timeline: list[dict],
    report: dict | None = None,
    history: list[dict] | None = None,
) -> dict:
    history = history or []
    profiles = cat_profiles_for_context()
    resolution = resolve_cat_context(question, timeline, history, profiles)
    if resolution["needs_clarification"]:
        return {"provider": "local", "text": clarification_text(resolution["cats"])}

    scoped_timeline = resolution["timeline"]
    range_name = (report or {}).get("range", "day") if isinstance(report, dict) else "day"
    report_data = build_range_report(scoped_timeline, range_name) if resolution["cat"] else (report or build_range_report(timeline, "day"))
    cat_context = resolution["cat"]
    local_profile_answer = answer_profile_question(question, cat_context)
    try:
        answer = call_minimax(question, scoped_timeline, report_data, history=history, cat_context=cat_context)
        return {"provider": "minimax", "text": answer}
    except Exception:
        if local_profile_answer:
            return {"provider": "local", "text": local_profile_answer}
        return {
            "provider": "local",
            "text": (
                f"{answer_owner_question(question, scoped_timeline, report_data)}\n\n"
                "MiniMax is taking too long, so Beenz used the local timeline summary."
            ),
        }


def resolve_cat_context(question: str, timeline: list[dict], history: list[dict], profiles: list[dict] | None = None) -> dict:
    cats = merge_cat_sources(profiles or [], cats_from_timeline(timeline))
    cat = detect_cat_in_text(question, cats)
    if cat is None and uses_contextual_reference(question):
        cat = detect_cat_in_history(history, cats, current_question=question)

    if cat:
        scoped = [event for event in timeline if event.get("catId") == cat["id"]]
        return {"cat": cat, "timeline": scoped, "needs_clarification": False, "cats": cats}

    if should_ask_which_cat(question, cats):
        return {"cat": None, "timeline": timeline, "needs_clarification": True, "cats": cats}

    return {"cat": None, "timeline": timeline, "needs_clarification": False, "cats": cats}


def cats_from_timeline(timeline: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for event in timeline:
        cat_id = str(event.get("catId") or "").strip()
        cat_name = str(event.get("catName") or "").strip()
        if not cat_id or not cat_name:
            continue
        by_id.setdefault(cat_id, {"id": cat_id, "name": cat_name})
    return sorted(by_id.values(), key=lambda item: item["name"].lower())


def answer_profile_question(question: str, cat: dict | None) -> str | None:
    if not cat:
        return None

    words = set(re.findall(r"[a-z0-9]+", question.lower()))
    name = cat.get("name", "This cat")
    if words & {"old", "age", "aged"} and cat.get("age"):
        return f"{name} is {cat['age']} old."
    if words & {"birthday", "birthdate", "born"} and cat.get("birthDate"):
        return f"{name}'s recorded birth date is {cat['birthDate']}."
    if words & {"camera", "device"} and cat.get("device"):
        return f"{name} is currently linked to {cat['device']}."
    return None


def cat_profiles_for_context() -> list[dict]:
    profiles: list[dict] = []
    for cat in get_public_cats():
        profiles.append(
            {
                "id": cat.get("id"),
                "name": cat.get("name"),
                "age": cat.get("age"),
                "birthDate": cat.get("birthDate"),
                "device": cat.get("device"),
            }
        )
    return profiles


def merge_cat_sources(primary: list[dict], secondary: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for cat in [*secondary, *primary]:
        cat_id = str(cat.get("id") or "").strip()
        name = str(cat.get("name") or "").strip()
        if not cat_id or not name:
            continue
        existing = by_id.get(cat_id, {})
        by_id[cat_id] = {**existing, **cat, "id": cat_id, "name": name}
    return sorted(by_id.values(), key=lambda item: item["name"].lower())


def detect_cat_in_text(text: str, cats: list[dict]) -> dict | None:
    lowered = text.lower()
    for cat in cats:
        name = cat["name"].lower()
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            return cat
    return None


def detect_cat_in_history(history: list[dict], cats: list[dict], current_question: str) -> dict | None:
    current = current_question.strip()
    skipped_current = False
    for message in reversed(history):
        text = str(message.get("text") or "").strip()
        if not skipped_current and text == current:
            skipped_current = True
            continue
        cat = detect_cat_in_text(text, cats)
        if cat:
            return cat
    return None


def uses_contextual_reference(question: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", question.lower()))
    return bool(words & SINGULAR_CAT_REFERENCES)


def should_ask_which_cat(question: str, cats: list[dict]) -> bool:
    if len(cats) <= 1:
        return False
    words = set(re.findall(r"[a-z0-9]+", question.lower()))
    if words & HOUSEHOLD_TERMS:
        return False
    return bool((words & CAT_SPECIFIC_TERMS) or (words & SINGULAR_CAT_REFERENCES))


def clarification_text(cats: list[dict]) -> str:
    names = [cat["name"] for cat in cats]
    if not names:
        return "Which cat are you asking about?"
    if len(names) == 1:
        return f"Do you mean {names[0]}?"
    return f"Which cat do you mean: {', '.join(names[:-1])}, or {names[-1]}?"
