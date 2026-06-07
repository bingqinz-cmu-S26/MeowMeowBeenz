"""Lightweight scored retrieval over the mood-centric cat timeline.

No external dependencies and no embeddings: events are ranked by keyword overlap,
mood-synonym matching, an optional time window ("last night", "this morning"),
an optional cat filter, and a recency boost. Right-sized for dozens of events and
fast enough to run on every live-chat turn.
"""

import re
from datetime import datetime, time, timedelta, timezone

from app.services.cat_timeline import all_events, all_events_async, find_cat, mood_index, reference_now

# Natural-language words -> mood ids. Lets "is she hungry?" hit the soliciting mood, etc.
MOOD_SYNONYMS: dict[str, str] = {
    "happy": "content", "relaxed": "content", "calm": "content", "purring": "content",
    "affectionate": "affectionate", "cuddly": "affectionate", "loving": "affectionate", "greeting": "affectionate",
    "hungry": "soliciting", "food": "soliciting", "feed": "soliciting", "begging": "soliciting", "wants": "soliciting",
    "playing": "playful", "playful": "playful", "hunting": "playful", "stalking": "playful", "toy": "playful",
    "curious": "curious", "investigating": "curious", "exploring": "curious", "alert": "curious",
    "restless": "restless", "frustrated": "restless", "pacing": "restless", "bored": "restless",
    "angry": "agitated", "annoyed": "agitated", "hissing": "agitated", "growling": "agitated", "defensive": "agitated", "aggressive": "agitated",
    "scared": "fearful", "afraid": "fearful", "anxious": "fearful", "fearful": "fearful", "hiding": "fearful", "nervous": "fearful",
    "distress": "distress", "distressed": "distress", "crying": "distress", "yowling": "distress", "pain": "distress", "hurt": "distress",
    "discomfort": "discomfort", "sore": "discomfort", "aching": "discomfort", "stiff": "discomfort", "limping": "discomfort",
    "territorial": "territorial", "guarding": "territorial", "warning": "territorial",
    "mating": "mating", "heat": "mating",
    "grooming": "grooming", "licking": "grooming", "scratching": "grooming", "cleaning": "grooming",
    "sleepy": "sleepy", "sleeping": "sleepy", "resting": "sleepy", "napping": "sleepy", "tired": "sleepy", "dozing": "sleepy",
}

STOPWORDS = {
    "the", "a", "an", "is", "was", "were", "are", "be", "been", "being", "did", "do", "does",
    "what", "whats", "how", "why", "when", "where", "who", "which", "my", "me", "i", "we",
    "she", "he", "it", "they", "them", "her", "his", "their", "of", "to", "in", "on", "at",
    "for", "and", "or", "with", "about", "doing", "up", "today", "now", "cat", "cats", "kitty",
    "been", "today's", "this", "that", "any", "some", "tell", "show", "give",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def detect_cat(question: str, cat: str | None, candidates: list[dict]) -> str | None:
    """Resolve which cat the question is about: explicit param wins, else scan names."""
    resolved = find_cat(cat)
    if resolved:
        return resolved["id"]
    lowered = question.lower()
    for event in candidates:
        name = event["catName"].lower()
        if name and re.search(rf"\b{re.escape(name)}\b", lowered):
            return event["catId"]
    return None


def detect_moods(question: str) -> set[str]:
    """Mood ids implied by the question, via synonyms and direct id/label mentions."""
    lowered = question.lower()
    hits: set[str] = set()
    for word, mood_id in MOOD_SYNONYMS.items():
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            hits.add(mood_id)
    for mood_id, meta in mood_index().items():
        if mood_id in lowered or meta.get("label", "").lower() in lowered:
            hits.add(mood_id)
    return hits


def _most_recent_night(now: datetime) -> tuple[datetime, datetime]:
    """The night block (21:00 -> 05:00) most relevant to `now`.

    If it's currently evening/night we mean the night in progress; otherwise the
    most recently completed night. Keeps 'last night' meaningful even when all the
    demo data sits on one calendar day."""
    start_day = now.date() if now.hour >= 21 else now.date() - timedelta(days=1)
    start = datetime.combine(start_day, time(21, 0), tzinfo=timezone.utc)
    end = datetime.combine(start_day + timedelta(days=1), time(5, 0), tzinfo=timezone.utc)
    return start, end


def detect_window(question: str, now: datetime) -> tuple[datetime, datetime] | None:
    """Parse a coarse time window from the question, relative to `now`. None = no window."""
    q = question.lower()
    today = now.date()
    yesterday = today - timedelta(days=1)

    def span(d, start_h, end_h):
        start = datetime.combine(d, time(start_h, 0), tzinfo=timezone.utc)
        if end_h >= 24:
            end = datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)
        else:
            end = datetime.combine(d, time(end_h - 1, 59, 59), tzinfo=timezone.utc)
        return start, end

    if any(phrase in q for phrase in ("last night", "tonight", "overnight", "night")):
        return _most_recent_night(now)
    if "morning" in q:
        return span(today, 5, 12)
    if "afternoon" in q:
        return span(today, 12, 17)
    if "evening" in q:
        return span(today, 17, 21)
    if "yesterday" in q:
        return span(yesterday, 0, 24)
    if "today" in q:
        return span(today, 0, 24)
    return None


def score_event(event: dict, tokens: list[str], moods: set[str], window, now: datetime) -> float:
    if event["when"] is None:
        return -1.0
    if window is not None:
        start, end = window
        if not (start <= event["when"] <= end):
            return -1.0  # outside an explicitly requested window -> excluded

    haystack = " ".join(
        [event["action"], event["description"], event["moodLabel"], event["moodSummary"]]
    ).lower()

    score = 0.0
    for token in tokens:
        if token in haystack:
            score += 2.0
    if event["mood"] in moods:
        score += 4.0

    # recency: newer events score slightly higher (decays over ~48h)
    age_hours = max(0.0, (now - event["when"]).total_seconds() / 3600.0)
    score += max(0.0, 1.5 - age_hours / 48.0)

    # a confident observation is marginally more worth surfacing
    score += event["confidence"] * 0.5
    return score


async def retrieve_events(question: str, cat: str | None = None, limit: int = 6) -> list[dict]:
    """Return the most relevant timeline events for a question, each with a `score`."""
    candidates = await all_events_async()
    if not candidates:
        candidates = all_events()
    now = reference_now(candidates)
    cat_id = detect_cat(question, cat, candidates)
    tokens = tokenize(question)
    moods = detect_moods(question)
    window = detect_window(question, now)

    if cat_id:
        candidates = [e for e in candidates if e["catId"] == cat_id]

    scored = []
    for event in candidates:
        s = score_event(event, tokens, moods, window, now)
        if s >= 0:
            scored.append((s, event))

    # When the question carries no signal (no tokens/moods/window), fall back to most recent.
    if not tokens and not moods and window is None:
        scored.sort(key=lambda pair: pair[1]["when"] or now, reverse=True)
    else:
        scored.sort(key=lambda pair: (pair[0], pair[1]["when"] or now), reverse=True)

    results = []
    for s, event in scored[:limit]:
        results.append({**event, "when": None, "score": round(s, 3)})  # drop datetime for JSON safety
    return results
