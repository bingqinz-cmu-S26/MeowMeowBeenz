from fastapi import APIRouter, HTTPException

from app.models.schemas import LiveKitTokenRequest
from app.services.livekit import BadRequestError, MissingLiveKitConfigError, create_livekit_token

router = APIRouter(prefix="/api/livekit-token", tags=["livekit"])


@router.post("")
async def livekit_token(payload: LiveKitTokenRequest):
    try:
        token_payload = create_livekit_token(payload.room, payload.identity)
        return {"ok": True, **token_payload}
    except MissingLiveKitConfigError as error:
        raise HTTPException(status_code=503, detail={"configured": False, "error": str(error)}) from error
    except BadRequestError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
