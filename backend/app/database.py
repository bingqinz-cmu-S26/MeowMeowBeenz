from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient | None:
    return _client


def get_database() -> AsyncIOMotorDatabase | None:
    if _client is None:
        return None
    return _client[settings.mongodb_db]


async def connect_to_mongo() -> bool:
    global _client
    if not settings.mongodb_uri:
        return False

    try:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
        await _client.admin.command("ping")
        return True
    except Exception:
        _client = None
        return False


async def close_mongo_connection() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
