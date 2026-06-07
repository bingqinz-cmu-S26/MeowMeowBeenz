from fastapi import APIRouter, Query

from app.database import get_database
from app.services.health_rules import build_range_report
from app.services.sample_data import create_seed_events
from app.services.mock_store import filter_events_by_cat

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("")
async def get_report(
    range: str = Query("day", pattern="^(day|week|month)$"),
    cat_id: str | None = Query(None),
):
    db = get_database()
    if db is None:
        events = create_seed_events()
    else:
        query = {"catId": cat_id} if cat_id else {}
        events = await db.events.find(query, {"_id": 0}).to_list(length=500)
    events = filter_events_by_cat(events, cat_id)
    report = build_range_report(events, range)
    return {"ok": True, "report": report}
