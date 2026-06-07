"""Loader for the mood-centric placeholder dataset (data/mockData.json).

This is a separate data model from the live-app timeline (state/intent/soundType).
It powers the retrieval layer that answers "what was my cat doing" during live chat.
Each timeline event is { mood, action, timestamp, confidence } with an optional description.
"""

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.config import settings

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


_INTENT_MOOD: dict[str, str] = {
    "food_seeking": "soliciting",
    "resting_or_low_energy": "sleepy",
    "play_or_social_engagement": "playful",
    "curious_exploration": "curious",
    "social_bonding": "affectionate",
    "activity_change": "restless",
    "anxious_shift": "fearful",
    "defensive_behavior": "agitated",
    "pain_or_discomfort": "distress",
    "self_care_or_discomfort": "grooming",
    "territorial_warning": "territorial",
    "routine_elimination": "content",
    "routine_observation": "content",
}


def _convert_app_event(raw: dict, moods: dict[str, dict]) -> dict:
    intent = str(raw.get("intent") or "").strip()
    mood = _INTENT_MOOD.get(intent, "content")
    mood_meta = moods.get(mood, {})
    timestamp = str(raw.get("time") or raw.get("timestamp") or "")
    return {
        "id": raw.get("id"),
        "catId": raw.get("catId", ""),
        "catName": raw.get("catName", ""),
        "mood": mood,
        "moodLabel": mood_meta.get("label", mood),
        "moodSummary": mood_meta.get("summary", ""),
        "action": str(raw.get("state") or raw.get("action") or "Observed").strip(),
        "timestamp": timestamp,
        "when": parse_timestamp(timestamp) if timestamp else None,
        "confidence": float(raw.get("confidence", 0.7) or 0.7),
        "description": str(raw.get("summary") or raw.get("description") or "").strip(),
    }


def _timeline_events(moods: dict[str, dict]) -> list[dict]:
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
    return events


@lru_cache(maxsize=1)
def all_events() -> list[dict]:
    """Flatten demo events for retrieval.

    Prefer `app.events` (full timeline used by the iOS app) when present; otherwise
    fall back to the mood-centric `cats[].timeline` entries.
    """
    moods = mood_index()
    app_events = load_data().get("app", {}).get("events", [])
    if app_events:
        events = [_convert_app_event(raw, moods) for raw in app_events if raw.get("time") or raw.get("timestamp")]
    else:
        events = _timeline_events(moods)

    events.sort(key=lambda e: e["when"] or datetime.min.replace(tzinfo=timezone.utc))
    return events


def reference_now(events: list[dict] | None = None) -> datetime:
    """The 'current time' for relative windows. Anchored to the latest event so that
    phrases like 'last night' / 'this morning' are meaningful against the static demo data."""
    timeline = all_events() if events is None else events
    times = [e["when"] for e in timeline if e["when"] is not None]
    return max(times) if times else datetime.now(timezone.utc)
