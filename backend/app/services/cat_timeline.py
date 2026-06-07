"""Loader for the mood-centric placeholder dataset (data/mockData.json).

This is a separate data model from the live-app timeline (state/intent/soundType).
It powers the retrieval layer that answers "what was my cat doing" during live chat.
Each timeline event is { mood, action, timestamp, confidence } with an optional description.
"""

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings
from app.database import get_database

# repo root: .../backend/app/services/cat_timeline.py -> parents[3] == repo root
_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "mockData.json"


def _data_path() -> Path:
    override = getattr(settings, "mock_data_path", "") or ""
    return Path(override) if override else _DEFAULT_PATH


def parse_timestamp(value: str) -> datetime:
    """Parse the ISO-8601 timestamps in the dataset (which use a trailing Z)."""
    text = str(value).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@lru_cache(maxsize=1)
def load_data() -> dict:
    """Load and cache the raw JSON document. Returns an empty shell if missing."""
    path = _data_path()
    if not path.exists():
        return {"version": 0, "moods": [], "cats": []}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def mood_index() -> dict[str, dict]:
    """Map mood id -> mood metadata (label, summary, tags)."""
    return {mood["id"]: mood for mood in load_data().get("moods", [])}


def get_moods() -> list[dict]:
    return load_data().get("moods", [])


def get_cats() -> list[dict]:
    """Cat profiles without their (large) timelines."""
    return [{k: v for k, v in cat.items() if k != "timeline"} for cat in load_data().get("cats", [])]


def find_cat(name_or_id: str | None) -> dict | None:
    """Resolve a cat by id or (case-insensitive) name."""
    if not name_or_id:
        return None
    needle = str(name_or_id).strip().lower()
    for cat in load_data().get("cats", []):
        if cat.get("id", "").lower() == needle or cat.get("name", "").lower() == needle:
            return cat
    return None


@lru_cache(maxsize=1)
def all_events() -> list[dict]:
    """Flatten every cat's timeline into a single list, enriched with cat + mood metadata.

    Each returned event carries: catId, catName, mood, moodLabel, moodSummary, action,
    timestamp (raw string), when (datetime), confidence, description (may be "").
    Sorted oldest -> newest.
    """
    moods = mood_index()
    events: list[dict] = []
    for cat in load_data().get("cats", []):
        for raw in cat.get("timeline", []):
            mood = moods.get(raw.get("mood", ""), {})
            events.append(
                {
                    "catId": cat.get("id", ""),
                    "catName": cat.get("name", ""),
                    "mood": raw.get("mood", ""),
                    "moodLabel": mood.get("label", raw.get("mood", "")),
                    "moodSummary": mood.get("summary", ""),
                    "action": raw.get("action", ""),
                    "timestamp": raw.get("timestamp", ""),
                    "when": parse_timestamp(raw["timestamp"]) if raw.get("timestamp") else None,
                    "confidence": float(raw.get("confidence", 0)),
                    "description": raw.get("description", ""),
                }
            )
    events.sort(key=lambda e: e["when"] or datetime.min.replace(tzinfo=timezone.utc))
    return events


def reference_now(events: list[dict] | None = None) -> datetime:
    """The 'current time' for relative windows. Anchored to the latest event so that
    phrases like 'last night' / 'this morning' are meaningful against the static demo data."""
    timeline = all_events() if events is None else events
    times = [e["when"] for e in timeline if e["when"] is not None]
    return max(times) if times else datetime.now(timezone.utc)


def _parse_event_time(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        text = str(raw).strip().replace("Z", "+00:00")
    except Exception:  # noqa: BLE001
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _infer_mood_from_runtime(event: dict) -> str:
    text = " ".join(
        [
            str(event.get("state", "")),
            str(event.get("intent", "")),
            str(event.get("behaviorLabel", "")),
            str(event.get("soundType", "")),
            str(event.get("summary", "")),
            str(event.get("suggestion", "")),
        ]
    ).lower()

    if any(token in text for token in ("eat", "nutrition", "nutrition", "maintenance_nutrition", "maintenance_feeding")):
        return "soliciting"
    if any(token in text for token in ("rest", "sleep", "lying", "inactive", "nap", "resting")):
        return "sleepy"
    if any(token in text for token in ("groom", "scratc", "shake", "lick")):
        return "grooming"
    if any(token in text for token in ("litter", "dig", "toilet", "box")):
        return "discomfort"
    if any(token in text for token in ("distress", "yowl", "cater", "cry", "hurt", "pain", "agony", "panicked")):
        return "distress"
    if any(token in text for token in ("fight", "hiss", "growl", "fight", "defensive", "agitat", "alert", "scared", "fear", "anxious")):
        return "agitated"
    if any(token in text for token in ("play", "hunt", "active", "walking", "jump", "run", "stalk")):
        return "playful"
    return "content"


def _normalize_live_event(raw: dict, fallback_cat: dict) -> dict | None:
    try:
        confidence = float(raw.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0

    mood_id = _infer_mood_from_runtime(raw)
    when = _parse_event_time(raw.get("time"))
    cat_id = str(fallback_cat.get("id", "cat")).strip() or "cat"
    cat_name = str(fallback_cat.get("name", "Cat")).strip() or "Cat"
    if cat_id.lower() == "none":
        cat_id = "cat"
    if cat_name.lower() == "none":
        cat_name = "Cat"
    state = str(raw.get("state", "")).strip()
    summary = str(raw.get("summary", "")).strip()
    action = state or summary or "Observed behavior"
    description = summary or action

    mood_lookup = mood_index()
    return {
        "catId": cat_id,
        "catName": cat_name,
        "mood": mood_id,
        "moodLabel": mood_lookup.get(mood_id, {}).get("label", mood_id),
        "moodSummary": mood_lookup.get(mood_id, {}).get("summary", ""),
        "action": action,
        "timestamp": str(raw.get("time", "")),
        "when": when,
        "confidence": confidence,
        "description": description,
    }


async def all_events_async() -> list[dict]:
    """Try to build live events from MongoDB first, then fall back to mock data."""
    db = get_database()
    if db is None:
        return all_events()

    events_raw = await db.events.find({}, {"_id": 0}).sort("time", -1).to_list(length=500)
    if not events_raw:
        return all_events()

    cats = await db.cats.find({}, {"_id": 0, "id": 1, "name": 1}).sort("created_at", 1).to_list(length=1)
    fallback_cat = {}
    if cats:
        fallback_cat = {"id": cats[0].get("id", "cat"), "name": cats[0].get("name", "Cat")}
    if not fallback_cat:
        defaults = get_cats()
        fallback_cat = defaults[0] if defaults else {"id": "luna", "name": "Luna"}

    normalized = []
    for raw in events_raw:
        if not isinstance(raw, dict):
            continue
        row = _normalize_live_event(raw, fallback_cat)
        if row:
            normalized.append(row)

    if not normalized:
        return all_events()
    normalized.sort(key=lambda event: event["when"] or datetime.min.replace(tzinfo=timezone.utc))
    return normalized
