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
