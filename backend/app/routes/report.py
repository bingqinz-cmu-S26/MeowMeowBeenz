from fastapi import APIRouter, Query

from app.database import get_database
from app.services.health_rules import build_range_report
from app.services.sample_data import create_seed_events

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("")
async def get_report(range: str = Query("day", pattern="^(day|week|month)$")):
    db = get_database()
    if db is None:
        events = create_seed_events()
    else:
        events = await db.events.find({}, {"_id": 0}).to_list(length=500)
    report = build_range_report(events, range)
    return {"ok": True, "report": report}
