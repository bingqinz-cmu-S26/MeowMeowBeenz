from app.database import get_database
from app.services.sample_data import CAT_PROFILES, create_seed_events


async def ensure_seed_data() -> None:
    db = get_database()
    if db is None:
        return

    await db.users.create_index("username", unique=True)
    await db.users.create_index("id", unique=True)

    cat_count = await db.cats.count_documents({})
    if cat_count == 0:
        await db.cats.insert_many(CAT_PROFILES)

    event_count = await db.events.count_documents({})
    if event_count == 0:
        await db.events.insert_many(create_seed_events())
