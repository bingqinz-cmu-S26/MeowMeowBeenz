import random
from datetime import datetime, timedelta, timezone

SCENARIO_CATALOG = {
    "live": {
        "state": "Alert and vocal",
        "intent": "attention_or_food_seeking",
        "behaviorLabel": "active_walking",
        "soundType": "repeated_meow",
        "confidence": 0.74,
        "riskLevel": "normal",
        "signals": ["unusual_vocalization"],
        "summary": "The cat is active and producing repeated meows, which often points to attention or food seeking.",
        "suggestion": "Check the usual routine first: food, water, door access, and recent play time.",
    },
    "lowActivity": {
        "state": "Extended resting",
        "intent": "resting_or_low_energy",
        "behaviorLabel": "inactive_lying.resting",
        "soundType": "quiet",
        "confidence": 0.82,
        "riskLevel": "watch",
        "signals": ["low_activity_alert"],
        "summary": "The cat has stayed in a resting posture with little movement compared with active periods.",
        "suggestion": "Watch appetite and litter behavior. If low activity persists, consider a vet check-in.",
    },
    "nightYowl": {
        "state": "Night vocalization",
        "intent": "attention_or_discomfort",
        "behaviorLabel": "inactive_lying.crouch",
        "soundType": "caterwauling",
        "confidence": 0.69,
        "riskLevel": "watch",
        "signals": ["unusual_vocalization"],
        "summary": "A high-intensity nighttime vocalization was detected while the cat appeared inactive.",
        "suggestion": "Check for immediate needs and monitor whether this repeats tonight.",
    },
    "litterConcern": {
        "state": "Repeated litter activity",
        "intent": "litter_box_attempt",
        "behaviorLabel": "maintenance_littering.digging",
        "soundType": "short_meow",
        "confidence": 0.77,
        "riskLevel": "watch",
        "signals": ["possible_litter_box_issue"],
        "summary": "The cat appears to be repeatedly digging or visiting the litter area without a clear output event.",
        "suggestion": "Check the litter box and monitor for urination or defecation events.",
    },
    "appetiteGap": {
        "state": "Food solicitation without eating",
        "intent": "food_seeking",
        "behaviorLabel": "active_rubbing",
        "soundType": "repeated_meow",
        "confidence": 0.71,
        "riskLevel": "watch",
        "signals": ["possible_appetite_change"],
        "summary": "The cat vocalized near a routine feeding context, but no eating event has been logged.",
        "suggestion": "Check food and water. If appetite remains low for 24 hours, consider contacting a vet.",
    },
    "grooming": {
        "state": "Focused grooming",
        "intent": "self_grooming_or_irritation",
        "behaviorLabel": "maintenance_scratching",
        "soundType": "quiet",
        "confidence": 0.73,
        "riskLevel": "watch",
        "signals": ["possible_skin_ear_discomfort"],
        "summary": "Repeated scratching or focused grooming was detected.",
        "suggestion": "Inspect the skin and ears if this repeats or appears intense.",
    },
    "conflict": {
        "state": "Resting with distress-like audio",
        "intent": "ambiguous_discomfort",
        "behaviorLabel": "inactive_lying.resting",
        "soundType": "distress_like_yowl",
        "confidence": 0.58,
        "riskLevel": "review",
        "signals": ["multimodal_conflict", "unusual_vocalization"],
        "summary": "Video suggests resting, but the vocal pattern sounds distress-like. The signals do not fully agree.",
        "suggestion": "Review the clip and check for visible discomfort before drawing conclusions.",
    },
    "eating": {
        "state": "Eating detected",
        "intent": "nutrition",
        "behaviorLabel": "maintenance_nutrition.eating",
        "soundType": "quiet",
        "confidence": 0.86,
        "riskLevel": "normal",
        "signals": [],
        "summary": "The cat appears to be eating with a steady posture and low vocal activity.",
        "suggestion": "Log this as a normal appetite signal.",
    },
    "play": {
        "state": "Playful movement",
        "intent": "play_or_social_engagement",
        "behaviorLabel": "active_playfight.playing",
        "soundType": "chirp",
        "confidence": 0.79,
        "riskLevel": "normal",
        "signals": [],
        "summary": "The cat is moving actively with playful vocal cues.",
        "suggestion": "This looks like a normal enrichment or social play moment.",
    },
}

SCENARIO_TYPES = [
    {"id": "lowActivity", "label": "Low activity"},
    {"id": "nightYowl", "label": "Night yowl"},
    {"id": "litterConcern", "label": "Litter concern"},
    {"id": "appetiteGap", "label": "Appetite gap"},
    {"id": "grooming", "label": "Grooming spike"},
    {"id": "conflict", "label": "A/V conflict"},
    {"id": "eating", "label": "Eating"},
    {"id": "play", "label": "Play"},
]

CAT_PROFILES = [
    {
    "id": "luna",
    "name": "Luna",
        "initials": "Lu",
    "age": "4 yrs",
        "breed": "Domestic shorthair",
    "room": "Kitchen window",
    "routine": "Breakfast, window watch, evening cuddle time",
        "accent": "#66d19e",
    },
    {
    "id": "milo",
    "name": "Milo",
        "initials": "Mi",
    "age": "2 yrs",
        "breed": "Tabby mix",
    "room": "Living room",
    "routine": "Long sleep blocks and stretch breaks",
        "accent": "#e4bd5b",
    },
    {
    "id": "saffron",
    "name": "Saffron",
        "initials": "Sa",
    "age": "8 mo",
        "breed": "Maine Coon mix",
    "room": "Bedroom",
    "routine": "Play bursts, snack patrol, quick naps",
        "accent": "#76c7d8",
    },
]


def normalize_event(input_data: dict) -> dict:
    return {
        "id": f"evt_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{random.randbytes(3).hex()}",
        "catId": input_data.get("catId", "luna"),
        "time": datetime.now(timezone.utc).isoformat(),
        "source": input_data.get("source", "live_capture"),
        "state": input_data.get("state", "Unknown state"),
        "intent": input_data.get("intent", "unknown"),
        "behaviorLabel": input_data.get("behaviorLabel", "unknown"),
        "soundType": input_data.get("soundType", "unknown"),
        "confidence": float(input_data.get("confidence", 0)),
        "riskLevel": input_data.get("riskLevel", "normal"),
        "signals": list(input_data.get("signals", [])),
        "summary": input_data.get("summary", "The model returned an uncertain observation."),
        "suggestion": input_data.get("suggestion", "Keep observing and add more context."),
    }


def create_scenario_event(scenario_type: str = "live") -> dict:
    scenario = SCENARIO_CATALOG.get(scenario_type, SCENARIO_CATALOG["live"])
    source = "live_capture" if scenario_type == "live" else "demo_scenario"
    cat_id = "luna"
    if scenario_type == "lowActivity":
        cat_id = "milo"
    if scenario_type == "nightYowl":
        cat_id = "saffron"
    if scenario_type == "litterConcern":
        cat_id = "milo"
    if scenario_type == "appetiteGap":
        cat_id = "luna"
    if scenario_type == "grooming":
        cat_id = "saffron"
    if scenario_type == "conflict":
        cat_id = "milo"
    if scenario_type == "play":
        cat_id = "milo"
    return normalize_event({**scenario, "catId": cat_id, "source": source})


def create_seed_events() -> list[dict]:
    now = datetime.now(timezone.utc)
    seed = [
        {"type": "eating", "minutes_ago": 520, "cat_id": "luna"},
        {"type": "play", "minutes_ago": 410, "cat_id": "milo"},
        {"type": "lowActivity", "minutes_ago": 180, "cat_id": "milo"},
        {"type": "nightYowl", "minutes_ago": 45, "cat_id": "saffron"},
        {"type": "conflict", "minutes_ago": 16, "cat_id": "milo"}
    ]
    events = []
    for item in seed:
        event = create_scenario_event(item["type"])
        if item.get("cat_id"):
            event["catId"] = item["cat_id"]
        event["time"] = (now - timedelta(minutes=item["minutes_ago"])).isoformat()
        events.append(event)
    return events
