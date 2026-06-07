from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from app.database import get_database
from app.deps.auth import get_current_user
from app.models.schemas import AuthLoginRequest, AuthRegisterRequest
from app.services.auth import (
    AuthError,
    DatabaseRequiredError,
    create_access_token,
    create_user_id,
    hash_password,
    normalize_username,
    public_user,
    require_database,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register(payload: AuthRegisterRequest):
    db = get_database()
    try:
        require_database(db)
        username = normalize_username(payload.username)
        password_hash = hash_password(payload.password)
    except DatabaseRequiredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AuthError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    display_name = (payload.display_name or username).strip()[:40] or username
    user = {
        "id": create_user_id(),
        "username": username,
        "password_hash": password_hash,
        "display_name": display_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await db.users.insert_one(user)
    except DuplicateKeyError as error:
        raise HTTPException(status_code=409, detail="Username already exists.") from error

    token = create_access_token(user["id"], user["username"])
    return {"ok": True, "user": public_user(user), "token": token}


@router.post("/login")
async def login(payload: AuthLoginRequest):
    db = get_database()
    try:
        require_database(db)
        username = normalize_username(payload.username)
    except DatabaseRequiredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except AuthError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    user = await db.users.find_one({"username": username})
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_access_token(user["id"], user["username"])
    return {"ok": True, "user": public_user(user), "token": token}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {"ok": True, "user": public_user(current_user)}
