from fastapi import APIRouter, HTTPException, Query

from app.database import get_database
from app.services.sample_data import SCENARIO_TYPES, create_scenario_event, create_seed_events, normalize_event
from app.services.mock_store import filter_events_by_cat

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(cat_id: str | None = Query(None)):
    db = get_database()
    if db is None:
        return {"ok": True, "events": filter_events_by_cat(create_seed_events(), cat_id), "source": "local"}
    query = {"catId": cat_id} if cat_id else {}
    events = await db.events.find(query, {"_id": 0}).sort("time", -1).to_list(length=500)
    return {"ok": True, "events": events, "source": "mongodb"}


@router.post("")
async def create_event(payload: dict):
    event = normalize_event(payload)
    db = get_database()
    if db is None:
        return {"ok": True, "event": event, "source": "local"}
    await db.events.insert_one(event)
    return {"ok": True, "event": event, "source": "mongodb"}


@router.post("/seed")
async def seed_events():
    events = create_seed_events()
    db = get_database()
    if db is None:
        return {"ok": True, "events": events, "source": "local"}
    await db.events.delete_many({})
    await db.events.insert_many(events)
    return {"ok": True, "events": events, "source": "mongodb"}


@router.post("/scenario/{scenario_type}")
async def add_scenario(scenario_type: str):
    if scenario_type not in {item["id"] for item in SCENARIO_TYPES} and scenario_type != "live":
        raise HTTPException(status_code=400, detail="Unknown scenario type.")
    event = create_scenario_event(scenario_type)
    db = get_database()
    if db is None:
        return {"ok": True, "event": event, "source": "local"}
    await db.events.insert_one(event)
    return {"ok": True, "event": event, "source": "mongodb"}


@router.delete("")
async def clear_events():
    db = get_database()
    if db is None:
        return {"ok": True, "cleared": True, "source": "local"}
    await db.events.delete_many({})
    return {"ok": True, "cleared": True, "source": "mongodb"}


@router.get("/scenarios")
async def list_scenarios():
    return {"ok": True, "scenarios": SCENARIO_TYPES}
