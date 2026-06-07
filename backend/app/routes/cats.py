from fastapi import APIRouter, Depends, HTTPException

from app.database import get_database
from app.deps.auth import get_current_user
from app.models.schemas import CreateCatRequest, UpdateCatRequest
from app.services.auth import DatabaseRequiredError, require_database
from app.services.cats import (
    CatError,
    build_cat_document,
    build_cat_update,
    parse_birth_date,
    public_cat,
    validate_device,
    validate_name,
)

router = APIRouter(prefix="/api/cats", tags=["cats"])


async def get_owned_cat(db, cat_id: str, current_user: dict) -> dict:
    cat = await db.cats.find_one({"id": cat_id, "owner_id": current_user["id"]}, {"_id": 0})
    if cat is None:
        raise HTTPException(status_code=404, detail="Cat not found.")
    if cat.get("owner_username") and cat.get("owner_username") != current_user["username"]:
        raise HTTPException(status_code=404, detail="Cat not found.")
    return cat


@router.get("")
async def list_cats(current_user: dict = Depends(get_current_user)):
    db = get_database()
    try:
        require_database(db)
    except DatabaseRequiredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    cats = await db.cats.find({"owner_id": current_user["id"]}, {"_id": 0}).sort("created_at", 1).to_list(length=50)
    visible_cats = []
    for cat in cats:
        if cat.get("owner_username") and cat.get("owner_username") != current_user["username"]:
            continue
        if not cat.get("owner_username"):
            await db.cats.update_one(
                {"id": cat["id"]},
                {"$set": {"owner_username": current_user["username"]}},
            )
            cat["owner_username"] = current_user["username"]
        visible_cats.append(public_cat(cat))
    return {"ok": True, "cats": visible_cats, "owner": current_user["username"]}


@router.get("/{cat_id}")
async def get_cat(cat_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    try:
        require_database(db)
    except DatabaseRequiredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    cat = await get_owned_cat(db, cat_id, current_user)
    return {"ok": True, "cat": public_cat(cat)}


@router.post("")
async def create_cat(payload: CreateCatRequest, current_user: dict = Depends(get_current_user)):
    db = get_database()
    try:
        require_database(db)
    except DatabaseRequiredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    try:
        name = validate_name(payload.name)
        birth_date = parse_birth_date(payload.birth_date)
        device = validate_device(payload.device)
    except CatError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    existing_count = await db.cats.count_documents({"owner_id": current_user["id"]})
    cat = build_cat_document(
        current_user["id"],
        current_user["username"],
        name,
        birth_date,
        device,
        existing_count,
    )
    await db.cats.insert_one(cat)
    return {"ok": True, "cat": public_cat(cat)}


@router.put("/{cat_id}")
async def update_cat(cat_id: str, payload: UpdateCatRequest, current_user: dict = Depends(get_current_user)):
    db = get_database()
    try:
        require_database(db)
    except DatabaseRequiredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    await get_owned_cat(db, cat_id, current_user)

    try:
        name = validate_name(payload.name)
        birth_date = parse_birth_date(payload.birth_date)
        device = validate_device(payload.device)
    except CatError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    updates = build_cat_update(name, birth_date, device)
    await db.cats.update_one({"id": cat_id, "owner_id": current_user["id"]}, {"$set": updates})
    updated = await get_owned_cat(db, cat_id, current_user)
    return {"ok": True, "cat": public_cat(updated)}
