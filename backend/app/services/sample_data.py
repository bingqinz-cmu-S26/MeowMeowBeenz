"""Backward-compatible re-exports for routes that still import sample_data."""

from app.services.mock_store import (
    SCENARIO_TYPES,
    create_scenario_event,
    create_seed_events,
    normalize_event,
)

SCENARIO_CATALOG = {item["id"]: item for item in SCENARIO_TYPES}
