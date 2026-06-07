from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any
import secrets

from app.services.cats import cat_initials, public_cat
from app.services.cat_timeline import all_events, load_data, mood_index

DEFAULT_CAT_ACCENTS = ["#66d19e", "#e4bd5b", "#76c7d8", "#ef7c73", "#d3c7a3"]

SCENARIO_TYPES = [
    {"id": "lowActivity", "label": "Low activity"},
    {"id": "nightYowl", "label": "Night yowl"},
    {"id": "litterConcern", "label": "Litter concern"},
    {"id": "appetiteGap", "label": "Appetite gap"},
    {"id": "grooming", "label": "Grooming spike"},
    {"id": "conflict", "label": "A/V conflict"},
    {"id": "eating", "label": "Eating"},
    {"id": "play", "label": "Play"},
    {"id": "live", "label": "Live check"},
]

_SCENARIO_TO_MOOD: dict[str, str] = {
    "live": "content",
    "lowActivity": "restless",
    "nightYowl": "distress",
    "litterConcern": "discomfort",
    "appetiteGap": "soliciting",
    "grooming": "grooming",
    "conflict": "agitated",
    "eating": "soliciting",
    "play": "playful",
}

_SCENARIO_TO_CAT: dict[str, str] = {
    "live": "luna",
    "lowActivity": "milo",
    "nightYowl": "saffron",
    "litterConcern": "milo",
    "appetiteGap": "luna",
    "grooming": "saffron",
    "conflict": "milo",
    "eating": "luna",
    "play": "milo",
}

_MOOD_TO_INTENT: dict[str, str] = {
    "content": "resting_or_low_energy",
    "affectionate": "social_bonding",
    "soliciting": "food_seeking",
    "playful": "play_or_social_engagement",
    "curious": "curious_exploration",
    "restless": "activity_change",
    "agitated": "defensive_behavior",
    "fearful": "anxious_shift",
    "distress": "pain_or_discomfort",
    "discomfort": "pain_or_discomfort",
    "territorial": "territorial_warning",
    "mating": "social_interest",
    "grooming": "self_care_or_discomfort",
    "sleepy": "resting_or_low_energy",
}

_MOOD_TO_SOUND: dict[str, str] = {
    "content": "soft_purr",
    "affectionate": "soft_purr",
    "soliciting": "repeated_meow",
    "playful": "chirp",
    "curious": "quiet",
    "restless": "short_meow",
    "agitated": "yowl",
    "fearful": "yowl",
    "distress": "distress_like_yowl",
    "discomfort": "distress_like_yowl",
    "territorial": "hiss",
    "mating": "soft_purr",
    "grooming": "quiet",
    "sleepy": "quiet",
}

_MOOD_TO_RISK: dict[str, str] = {
    "distress": "review",
    "discomfort": "review",
    "agitated": "watch",
    "fearful": "watch",
    "restless": "watch",
    "territorial": "watch",
}

_RUNTIME_CATS: list[dict] | None = None
_RUNTIME_EVENTS: list[dict] | None = None


def _birth_date_for_age(age_years: Any) -> str:
    try:
        years = int(age_years)
    except (TypeError, ValueError):
        years = 0

    if years < 0:
        years = 0

    today = date.today()
    year = max(1, today.year - years)
    return date(year, 1, 1).isoformat()


def _time_to_sort_key(value: str) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _new_event_id(cat_id: str) -> str:
    return f"evt_{cat_id}_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{secrets.token_hex(4)}"


def _sort_events(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda item: _time_to_sort_key(item.get("time", "")), reverse=True)


def _seed_cats() -> list[dict]:
    seeded = []
    for index, cat in enumerate(load_data().get("cats", [])):
        cat_id = str(cat.get("id") or f"cat_{index}").strip()
        if not cat_id:
            cat_id = f"cat_{index}"
        name = str(cat.get("name") or f"Cat {index + 1}").strip() or f"Cat {index + 1}"
        age_years = cat.get("ageYears", 0)
        seeded.append(
            {
                "id": cat_id,
                "owner_id": None,
                "owner_username": None,
                "name": name,
                "birth_date": _birth_date_for_age(age_years),
                "device": cat.get("device"),
                "initials": cat_initials(name),
                "accent": cat.get("accent") or DEFAULT_CAT_ACCENTS[index % len(DEFAULT_CAT_ACCENTS)],
            }
        )
    return seeded


def _runtime_cats() -> list[dict]:
    global _RUNTIME_CATS
    if _RUNTIME_CATS is None:
        _RUNTIME_CATS = _seed_cats()
    return _RUNTIME_CATS


def _runtime_events() -> list[dict]:
    global _RUNTIME_EVENTS
    if _RUNTIME_EVENTS is None:
        _RUNTIME_EVENTS = []
    return _RUNTIME_EVENTS


def get_public_cats(owner_id: str | None = None, owner_username: str | None = None) -> list[dict]:
    out: list[dict] = []
    for cat in _runtime_cats():
        cat_record = dict(cat)
        if owner_id is not None:
            cat_record["owner_id"] = owner_id
        if owner_username is not None:
            cat_record["owner_username"] = owner_username
        out.append(public_cat(cat_record))
    return out


def get_cats() -> list[dict]:
    return deepcopy(_runtime_cats())


def get_cat_by_id(cat_id: str) -> dict | None:
    target = str(cat_id or "").strip().lower()
    for cat in _runtime_cats():
        if str(cat.get("id", "")).strip().lower() == target:
            return cat
    return None


def add_cat(cat_record: Mapping[str, Any]) -> dict:
    record = dict(cat_record)
    _runtime_cats().append(record)
    return record


def update_cat(cat_id: str, updates: Mapping[str, Any]) -> dict | None:
    target = str(cat_id or "").strip().lower()
    cats = _runtime_cats()
    for cat in cats:
        if str(cat.get("id", "")).strip().lower() == target:
            for key in ("name", "birth_date", "device"):
                if key in updates:
                    cat[key] = updates[key]
            if "name" in updates and updates["name"]:
                cat["initials"] = cat_initials(str(updates["name"]).strip())
            return cat
    return None


def _to_runtime_cat_snapshot() -> list[dict]:
    return get_public_cats()


def _find_timeline_anchor(mood: str | None, preferred_cat_id: str | None) -> dict:
    mood_key = str(mood or "").strip().lower()
    timeline = all_events()

    if preferred_cat_id:
        for event in reversed(timeline):
            if str(event.get("catId", "")).strip().lower() == str(preferred_cat_id).strip().lower() and event.get(
                "mood"
            ) == mood_key:
                return event

    if mood_key:
        for event in reversed(timeline):
            if event.get("mood") == mood_key:
                return event

    return timeline[-1] if timeline else {
        "catId": preferred_cat_id or (_runtime_cats()[0]["id"] if _runtime_cats() else "cat_0"),
        "mood": mood_key or "content",
        "action": "Observed behavior",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence": 0.62,
        "description": "No exact template was found, so a neutral observation was used.",
    }


def _derive_behavior_label(mood: str, action: str) -> str:
    action_key = action.lower()

    if "eating" in action_key:
        return "maintenance_nutrition.eating"
    if any(token in action_key for token in ("stalking", "playing", "pouncing", "play", "chasing", "chase", "stalk")):
        return "active_playfight.playing"
    if any(token in action_key for token in ("lick", "scratching", "grooming", "licking")):
        return "maintenance_scratching"
    if any(token in action_key for token in ("pacing", "facing", "guarding", "moving", "restless", "hissing", "growling", "growl")):
        return "active_walking"
    if any(token in action_key for token in ("sleep", "lying", "nap", "sunbathing", "resting", "dozing")):
        return "inactive_lying.resting"

    if mood in {"playful", "curious", "mating"}:
        return "active_playfight.playing"
    if mood in {"soliciting", "affectionate", "content", "sleepy"}:
        return "inactive_lying.resting"
    if mood in {"agitated", "fearful", "territorial", "distress", "discomfort"}:
        return "active_walking"
    return "inactive_lying.resting"


def _event_from_timeline_event(event: Mapping[str, Any], source: str = "mockData") -> dict:
    mood = str(event.get("mood") or "content").strip().lower()
    action = str(event.get("action") or "Observed").strip()
    mood_meta = mood_index().get(mood, {})
    cat_id = str(event.get("catId") or "").strip().lower() or (_runtime_cats()[0]["id"] if _runtime_cats() else "cat_0")
    timestamp = str(event.get("timestamp") or datetime.now(timezone.utc).isoformat())
    summary = str(event.get("description") or mood_meta.get("summary", "Observed behavior")).strip()
    suggestion = f"Watch for pattern changes around {action.lower()} if this repeats frequently."

    return {
        "id": f"evt_{cat_id}_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{secrets.token_hex(2)}",
        "catId": cat_id,
        "time": timestamp,
        "source": source,
        "state": action,
        "intent": _MOOD_TO_INTENT.get(mood, "routine_observation"),
        "behaviorLabel": _derive_behavior_label(mood, action),
        "soundType": _MOOD_TO_SOUND.get(mood, "quiet"),
        "confidence": float(event.get("confidence", 0.7) or 0.7),
        "riskLevel": _MOOD_TO_RISK.get(mood, "normal"),
        "signals": [],
        "summary": summary,
        "suggestion": suggestion,
    }


def _normalize_event_payload(payload: Mapping[str, Any], source: str = "local") -> dict:
    cat_id = str(payload.get("catId") or "").strip().lower()
    if not cat_id or not get_cat_by_id(cat_id):
        default_cat = _runtime_cats()[0]["id"] if _runtime_cats() else "cat_0"
        cat_id = default_cat

    raw_time = payload.get("time")
    if not raw_time:
        raw_time = datetime.now(timezone.utc).isoformat()

    event: dict[str, Any] = {
        "id": str(payload.get("id") or _new_event_id(cat_id)),
        "catId": cat_id,
        "time": str(raw_time),
        "source": str(payload.get("source") or source),
        "state": str(payload.get("state") or "Observed").strip() or "Observed",
        "intent": str(payload.get("intent") or "routine_observation").strip() or "routine_observation",
        "behaviorLabel": str(payload.get("behaviorLabel") or "inactive_lying.resting").strip() or "inactive_lying.resting",
        "soundType": str(payload.get("soundType") or "quiet").strip() or "quiet",
        "confidence": max(0.0, min(1.0, float(payload.get("confidence", 0.5) or 0.5))),
        "riskLevel": str(payload.get("riskLevel") or "normal").strip() or "normal",
        "signals": [str(item).strip() for item in (payload.get("signals") or []) if str(item).strip()],
        "summary": str(payload.get("summary") or "Observation logged by user input.").strip(),
        "suggestion": str(payload.get("suggestion") or "Keep monitoring and add context when possible.").strip(),
    }

    if event["riskLevel"] not in {"normal", "watch", "review"}:
        event["riskLevel"] = "normal"

    return event


def _seed_events_from_mock() -> list[dict]:
    events = [_event_from_timeline_event(event, source="mockData") for event in all_events()]
    if not events:
        events = []
    return _sort_events(events)


def get_events() -> list[dict]:
    return _sort_events(deepcopy(_runtime_events()))


def add_event(payload: Mapping[str, Any], source: str = "local") -> dict:
    event = _normalize_event_payload(payload, source=source)
    events = _runtime_events()
    events.insert(0, event)
    return event


def reset_events() -> list[dict]:
    global _RUNTIME_EVENTS
    _RUNTIME_EVENTS = _seed_events_from_mock()
    return deepcopy(_RUNTIME_EVENTS)


def clear_events() -> list[dict]:
    _RUNTIME_EVENTS = []
    return []


def scenario_types() -> list[dict]:
    return deepcopy(SCENARIO_TYPES)


def scenario_type_ids() -> set[str]:
    return {item["id"] for item in SCENARIO_TYPES}


def create_scenario_event(scenario_type: str = "live") -> dict:
    scenario = str(scenario_type or "live").strip()
    mood = _SCENARIO_TO_MOOD.get(scenario, "content")
    cat_id = _SCENARIO_TO_CAT.get(scenario) or (_runtime_cats()[0]["id"] if _runtime_cats() else "cat_0")
    event = _find_timeline_anchor(mood, preferred_cat_id=cat_id)
    generated = _event_from_timeline_event(event, source="scenario")
    generated.update(
        {
            "catId": cat_id,
            "time": datetime.now(timezone.utc).isoformat(),
            "id": _new_event_id(cat_id),
            "source": "scenario",
            "riskLevel": "review" if mood in {"distress", "discomfort"} else _MOOD_TO_RISK.get(mood, "normal"),
            "intent": _MOOD_TO_INTENT.get(mood, "routine_observation"),
        }
    )
    if scenario == "eating":
        generated["behaviorLabel"] = "maintenance_nutrition.eating"
        generated["soundType"] = "quiet"
        generated["state"] = "Eating detected"
        generated["summary"] = "The cat appears to be eating with a steady posture and low vocal activity."
        generated["signals"] = []
    if scenario == "play":
        generated["behaviorLabel"] = "active_playfight.playing"
        generated["soundType"] = "chirp"
        generated["state"] = "Playful movement"
        generated["summary"] = "This looks like a normal enrichment or social play moment."
    if scenario == "conflict":
        generated["riskLevel"] = "review"
        generated["signals"] = ["multimodal_conflict", "unusual_vocalization"]
    return generated


def create_seed_events() -> list[dict]:
    return reset_events()


def normalize_event(payload: Mapping[str, Any], source: str = "local") -> dict:
    return _normalize_event_payload(payload, source=source)


def reset_cats() -> list[dict]:
    global _RUNTIME_CATS
    _RUNTIME_CATS = _seed_cats()
    return get_cats()


def seed_default_state() -> None:
    reset_cats()
    reset_events()


def cat_state_snapshot_for_user(owner_id: str | None = None, owner_username: str | None = None) -> list[dict]:
    return get_public_cats(owner_id=owner_id, owner_username=owner_username)
