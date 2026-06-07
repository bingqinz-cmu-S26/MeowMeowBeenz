from datetime import datetime, timezone

SIGNAL_COPY = {
    "possible_appetite_change": {
        "title": "Possible appetite change",
        "suggestion": "Check food and water. If appetite stays low for 24 hours or combines with lethargy, consider contacting a vet.",
    },
    "possible_litter_box_issue": {
        "title": "Possible litter box issue",
        "suggestion": "Check the litter box and watch for repeated attempts, straining, or missing output events.",
    },
    "low_activity_alert": {
        "title": "Activity lower than expected",
        "suggestion": "Encourage gentle interaction and monitor appetite, litter behavior, and posture.",
    },
    "possible_skin_ear_discomfort": {
        "title": "Possible skin or ear discomfort",
        "suggestion": "Inspect for repeated scratching, head shaking, or focused grooming if this continues.",
    },
    "unusual_vocalization": {
        "title": "Unusual vocalization pattern",
        "suggestion": "Check immediate needs and monitor whether the vocal pattern repeats or intensifies.",
    },
    "multimodal_conflict": {
        "title": "Audio-video mismatch",
        "suggestion": "Review the moment manually. Conflicting signals should be treated as uncertain, not diagnostic.",
    },
}


def build_range_report(events: list[dict], range_name: str = "day") -> dict:
    scoped = filter_by_range(events, range_name)
    counts = count_events(scoped)
    alerts = alerts_from_event_signals(scoped) + alerts_from_behavior_mix(scoped, counts)
    deduped = dedupe_alerts(alerts)
    overall = choose_overall_level(deduped)
    return {
        "dateLabel": label_for_range(range_name),
        "range": range_name,
        "totalEvents": len(scoped),
        "counts": counts,
        "alerts": deduped,
        "overall": overall,
        "summary": build_summary(scoped, deduped, overall),
    }


def filter_by_range(events: list[dict], range_name: str) -> list[dict]:
    now = datetime.now(timezone.utc).timestamp() * 1000
    days = 30 if range_name == "month" else 7 if range_name == "week" else 1
    start = now - days * 24 * 60 * 60 * 1000
    return [e for e in events if parse_time(e.get("time", "")) >= start]


def parse_time(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return 0


def label_for_range(range_name: str) -> str:
    if range_name == "month":
        return "Last 30 days"
    if range_name == "week":
        return "Last 7 days"
    return datetime.now().strftime("%A, %b %d")


def count_events(events: list[dict]) -> dict:
    counts = {
        "eating": 0,
        "litter": 0,
        "active": 0,
        "resting": 0,
        "grooming": 0,
        "vocal": 0,
        "review": 0,
    }
    for event in events:
        label = event.get("behaviorLabel", "")
        sound = event.get("soundType", "")
        if "eating" in label or "nutrition" in label:
            counts["eating"] += 1
        if "littering" in label:
            counts["litter"] += 1
        if is_active_behavior(label):
            counts["active"] += 1
        if "inactive" in label or "resting" in label or "lying" in label:
            counts["resting"] += 1
        if "grooming" in label or "scratching" in label or "shake" in label:
            counts["grooming"] += 1
        if any(token in sound for token in ("meow", "yowl", "caterwaul", "chirp")):
            counts["vocal"] += 1
        if event.get("riskLevel") == "review":
            counts["review"] += 1
    return counts


def is_active_behavior(label: str) -> bool:
    if "inactive" in label:
        return False
    return any(token in label for token in ("active", "walking", "jumping", "climbing", "play"))


def alerts_from_event_signals(events: list[dict]) -> list[dict]:
    alerts = []
    for event in events:
        for signal in event.get("signals", []):
            alerts.append(create_alert(signal, [event.get("summary", "")], float(event.get("confidence", 0))))
    return alerts


def alerts_from_behavior_mix(events: list[dict], counts: dict) -> list[dict]:
    if not events:
        return []
    alerts = []
    if counts["eating"] == 0 and len(events) >= 3:
        alerts.append(create_alert("possible_appetite_change", ["No eating event has been logged in today's timeline."], 0.62))
    if counts["resting"] >= 3 and counts["active"] <= 1:
        alerts.append(
            create_alert(
                "low_activity_alert",
                [f"Resting events ({counts['resting']}) are dominating active events ({counts['active']})."],
                0.67,
            )
        )
    if counts["litter"] >= 2 and not any(
        "urinating" in e.get("behaviorLabel", "") or "defecating" in e.get("behaviorLabel", "") for e in events
    ):
        alerts.append(
            create_alert(
                "possible_litter_box_issue",
                ["Repeated litter activity appears without a logged urination or defecation event."],
                0.7,
            )
        )
    if counts["grooming"] >= 2:
        alerts.append(
            create_alert(
                "possible_skin_ear_discomfort",
                [f"Focused grooming/scratching events appeared {counts['grooming']} times."],
                0.64,
            )
        )
    if counts["vocal"] >= 3:
        alerts.append(
            create_alert("unusual_vocalization", [f"Vocal events appeared {counts['vocal']} times today."], 0.66)
        )
    return alerts


def create_alert(signal: str, evidence: list[str], confidence: float) -> dict:
    copy = SIGNAL_COPY.get(
        signal,
        {
            "title": "Behavior change worth monitoring",
            "suggestion": "Keep observing and collect more context before drawing conclusions.",
        },
    )
    return {
        "signal": signal,
        "level": "review" if signal == "multimodal_conflict" else "watch",
        "title": copy["title"],
        "evidence": evidence,
        "suggestion": copy["suggestion"],
        "confidence": confidence,
    }


def dedupe_alerts(alerts: list[dict]) -> list[dict]:
    by_signal: dict[str, dict] = {}
    for alert in alerts:
        existing = by_signal.get(alert["signal"])
        if not existing:
            by_signal[alert["signal"]] = alert
            continue
        by_signal[alert["signal"]] = {
            **existing,
            "level": "review" if existing["level"] == "review" or alert["level"] == "review" else "watch",
            "confidence": max(existing["confidence"], alert["confidence"]),
            "evidence": (existing["evidence"] + alert["evidence"])[:4],
        }
    return list(by_signal.values())


def choose_overall_level(alerts: list[dict]) -> str:
    if any(alert["level"] == "review" for alert in alerts):
        return "review"
    if alerts:
        return "watch"
    return "normal"


def build_summary(events: list[dict], alerts: list[dict], overall: str) -> str:
    if not events:
        return "No observations have been logged yet. Start a live analysis or add demo events to build a baseline."
    if overall == "review":
        return "Some signals disagree or need human review. This is not a diagnosis, but it is worth checking the recent clips."
    if overall == "watch":
        return "Your cats have behavior changes worth monitoring today. Review the evidence and watch whether the pattern continues."
    return "Today's observed behavior looks within the normal demo baseline."
