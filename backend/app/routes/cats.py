from fastapi import APIRouter, Depends, HTTPException

from app.deps.auth import get_current_user
from app.models.schemas import CreateCatRequest, UpdateCatRequest
from app.services.cats import (
    CatError,
    build_cat_document,
    build_cat_update,
    parse_birth_date,
    public_cat,
    validate_device,
    validate_name,
)
from app.services.mock_store import add_cat, get_cat_by_id, get_cats, update_cat as persist_cat_update
from app.services.mock_store import cat_state_snapshot_for_user

router = APIRouter(prefix="/api/cats", tags=["cats"])


def _get_owned_cat(cat_id: str, current_user: dict) -> dict:
    cat = get_cat_by_id(cat_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Cat not found.")
    if not cat.get("owner_id") and not cat.get("owner_username"):
        cat["owner_id"] = current_user["id"]
        cat["owner_username"] = current_user["username"]
    if cat.get("owner_id") and cat.get("owner_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Cat not found.")
    if cat.get("owner_username") and cat.get("owner_username") != current_user["username"]:
        raise HTTPException(status_code=404, detail="Cat not found.")
    if not cat.get("owner_id"):
        cat["owner_id"] = current_user["id"]
    if not cat.get("owner_username"):
        cat["owner_username"] = current_user["username"]
    return cat


@router.get("")
async def list_cats(current_user: dict = Depends(get_current_user)):
    visible_cats = []
    for cat in get_cats():
        owned_cat = get_cat_by_id(cat.get("id"))
        if owned_cat is None:
            continue
        if not owned_cat.get("owner_id") and not owned_cat.get("owner_username"):
            owned_cat["owner_id"] = current_user["id"]
            owned_cat["owner_username"] = current_user["username"]
        if owned_cat.get("owner_id") and owned_cat.get("owner_id") != current_user["id"]:
            continue
        if owned_cat.get("owner_username") and owned_cat.get("owner_username") != current_user["username"]:
            continue
        if not owned_cat.get("owner_id"):
            owned_cat["owner_id"] = current_user["id"]
        if not owned_cat.get("owner_username"):
            owned_cat["owner_username"] = current_user["username"]
        visible_cats.append(public_cat(owned_cat))
    return {"ok": True, "cats": visible_cats, "owner": current_user["username"]}


@router.get("/public")
async def list_public_cats():
    return {"ok": True, "cats": cat_state_snapshot_for_user()}


@router.get("/{cat_id}")
async def get_cat(cat_id: str, current_user: dict = Depends(get_current_user)):
    cat = _get_owned_cat(cat_id, current_user)
    return {"ok": True, "cat": public_cat(cat)}


@router.post("")
async def create_cat(payload: CreateCatRequest, current_user: dict = Depends(get_current_user)):
    try:
        name = validate_name(payload.name)
        birth_date = parse_birth_date(payload.birth_date)
        device = validate_device(payload.device)
    except CatError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    existing_count = len(get_cats())
    cat = build_cat_document(
        current_user["id"],
        current_user["username"],
        name,
        birth_date,
        device,
        existing_count,
    )
    add_cat(cat)
    return {"ok": True, "cat": public_cat(cat)}


@router.put("/{cat_id}")
async def update_cat(cat_id: str, payload: UpdateCatRequest, current_user: dict = Depends(get_current_user)):
    _get_owned_cat(cat_id, current_user)

    try:
        name = validate_name(payload.name)
        birth_date = parse_birth_date(payload.birth_date)
        device = validate_device(payload.device)
    except CatError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    updates = build_cat_update(name, birth_date, device)
    updated = persist_cat_update(cat_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Cat not found.")
    return {"ok": True, "cat": public_cat(updated)}
