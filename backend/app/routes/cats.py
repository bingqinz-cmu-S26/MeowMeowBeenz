from fastapi import APIRouter

from app.database import get_database
from app.services.sample_data import CAT_PROFILES

router = APIRouter(prefix="/api/cats", tags=["cats"])


@router.get("")
async def list_cats():
    db = get_database()
    if db is None:
        return {"ok": True, "cats": CAT_PROFILES, "source": "local"}
    cats = await db.cats.find({}, {"_id": 0}).to_list(length=20)
    return {"ok": True, "cats": cats or CAT_PROFILES, "source": "mongodb"}
