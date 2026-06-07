from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_mongo_connection, connect_to_mongo, get_database
from app.routes import agent, auth, cats, events, livekit, report, analyze_clip
from app.services.seed import ensure_seed_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    connected = await connect_to_mongo()
    if connected:
        await ensure_seed_data()
    yield
    await close_mongo_connection()


app = FastAPI(title="MeowMeowBeenz API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cats.router)
app.include_router(events.router)
app.include_router(report.router)
app.include_router(agent.router)
app.include_router(livekit.router)
app.include_router(analyze_clip.router)


@app.get("/api/health")
async def health_check():
    db = get_database()
    return {
        "ok": True,
        "service": "meowmeowbeenz-api",
        "mongodb": "connected" if db is not None else "not_configured",
    }
