from fastapi import APIRouter, HTTPException

from app.models.schemas import LiveKitTokenRequest
from app.services.livekit import BadRequestError, MissingLiveKitConfigError, create_livekit_token
from app.services.voice_worker import ensure_voice_worker_on_demand, stop_voice_worker
from app.config import settings

router = APIRouter(prefix="/api/livekit-token", tags=["livekit"])


@router.post("")
async def livekit_token(payload: LiveKitTokenRequest):
    try:
        ensure_voice_worker_on_demand()
        token_payload = create_livekit_token(payload.room, payload.identity)
        return {"ok": True, **token_payload}
    except MissingLiveKitConfigError as error:
        raise HTTPException(status_code=503, detail={"configured": False, "error": str(error)}) from error
    except BadRequestError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail={"configured": True, "error": str(error)}) from error


@router.post("/stop")
async def stop_livekit_worker():
    if settings.start_voice_worker:
        return {
            "ok": True,
            "stopped": False,
            "reason": "managed_mode",
            "message": "LiveKit worker is managed by START_VOICE_WORKER. Use backend restart to stop it.",
        }

    stopped = stop_voice_worker()
    return {
        "ok": True,
        "stopped": stopped,
        "message": "LiveKit voice worker stopped." if stopped else "No LiveKit voice worker was running.",
    }
