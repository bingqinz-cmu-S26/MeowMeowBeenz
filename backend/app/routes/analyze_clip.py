from email.message import Message
from email.parser import BytesParser
from email.policy import default
from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from app.database import get_database
from app.deps.auth import get_optional_user
from app.models.schemas import ClipAnalysisResponse, ClipFileInfo, UploadGalleryItem
from app.services.video_analysis import analyze_video_clip

router = APIRouter(prefix="/api/analyze-clip", tags=["analyze-clip"])


@router.post("")
async def analyze_clip(
    request: Request,
    current_user: dict | None = Depends(get_optional_user),
) -> ClipAnalysisResponse:
    content_type = (request.headers.get("content-type") or "").strip()
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Uploaded video is empty.")

    if content_type.startswith("multipart/form-data"):
        file_data, filename, media_type = _extract_file_from_multipart(content_type, body)
        if not file_data:
            raise HTTPException(status_code=400, detail="No file field named 'clip' was found in the multipart payload.")
    else:
        if not content_type.startswith("video/"):
            raise HTTPException(status_code=400, detail="Only video uploads are supported for clip analysis.")
        file_data = body
        filename = request.headers.get("x-filename") or "upload.mov"
        media_type = content_type

    if not file_data:
        raise HTTPException(status_code=400, detail="Uploaded video is empty.")

    result = analyze_video_clip(
        filename=filename,
        file_data=file_data,
        mime_type=media_type,
    )

    event = result.get("event")
    db = get_database()
    gallery_item = None
    if db is not None:
        if isinstance(event, dict):
            await db.events.insert_one(event)
        gallery_item = await _save_gallery_item(
            request=request,
            db=db,
            current_user=current_user,
            filename=filename,
            media_type=media_type,
            file_data=file_data,
            result=result,
        )

    return ClipAnalysisResponse(
        ok=True,
        provider=result["provider"],
        text=result["text"],
        rawText=result.get("rawText"),
        file=ClipFileInfo(
            name=filename,
            type=media_type,
            size=len(file_data),
        ),
        event=result.get("event"),
        analysis=result.get("analysis"),
        galleryItem=gallery_item,
    )


@router.get("/gallery")
async def list_gallery(current_user: dict | None = Depends(get_optional_user)):
    db = get_database()
    if db is None:
        return {"ok": True, "items": [], "source": "local"}

    query = _owner_query(current_user)
    items = await db.upload_gallery.find(query, {"_id": 0}).sort("createdAt", -1).to_list(length=100)
    return {"ok": True, "items": items, "source": "mongodb"}


@router.delete("/gallery/{item_id}")
async def delete_gallery_item(item_id: str, current_user: dict | None = Depends(get_optional_user)):
    db = get_database()
    if db is None:
        return {"ok": True, "deleted": False, "source": "local"}

    query = {"id": item_id, **_owner_query(current_user)}
    item = await db.upload_gallery.find_one(query, {"_id": 0})
    if item is None:
        raise HTTPException(status_code=404, detail="Gallery item not found.")

    await db.upload_gallery.delete_one(query)
    video_file_id = item.get("videoFileId")
    if video_file_id:
        try:
            await AsyncIOMotorGridFSBucket(db).delete(ObjectId(video_file_id))
        except (InvalidId, Exception):
            pass
    return {"ok": True, "deleted": True, "source": "mongodb"}


@router.get("/gallery/{item_id}/video")
async def stream_gallery_video(item_id: str, request: Request):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=404, detail="Video storage is not configured.")

    item = await db.upload_gallery.find_one({"id": item_id}, {"_id": 0})
    if item is None or not item.get("videoFileId"):
        raise HTTPException(status_code=404, detail="Video not found.")

    try:
        grid_out = await AsyncIOMotorGridFSBucket(db).open_download_stream(ObjectId(item["videoFileId"]))
    except (InvalidId, Exception) as error:
        raise HTTPException(status_code=404, detail="Video not found.") from error

    file_size = grid_out.length
    start, end = _range_bounds(request.headers.get("range"), file_size)
    if start:
        grid_out.seek(start)
    remaining = end - start + 1

    async def chunks():
        nonlocal remaining
        while True:
            if remaining <= 0:
                break
            chunk = await grid_out.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk

    headers = {
        "Content-Disposition": f'inline; filename="{item.get("filename") or "upload.mov"}"',
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
    }
    status_code = 200
    if request.headers.get("range"):
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        status_code = 206
    return StreamingResponse(
        chunks(),
        media_type=item.get("mimeType") or "video/mp4",
        headers=headers,
        status_code=status_code,
    )


def _extract_file_from_multipart(content_type: str, body: bytes) -> tuple[bytes, str, str]:
    boundary = _boundary_value(content_type)
    if not boundary:
        raise HTTPException(status_code=400, detail="Malformed multipart content-type.")

    wrapped = f"Content-Type: {content_type}\r\n\r\n".encode() + body
    message: Message = BytesParser(policy=default).parsebytes(wrapped)
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition") or ""
        filename = part.get_param("filename", header="content-disposition") or part.get_filename() or ""
        if name != "clip" or not filename:
            continue
        data = part.get_payload(decode=True) or b""
        return data, filename, part.get_content_type()
    return b"", "", ""


def _boundary_value(content_type: str) -> str:
    if "boundary=" not in content_type.lower():
        return ""
    parts = [part.strip() for part in content_type.split(";")]
    for param in parts:
        if not param.lower().startswith("boundary="):
            continue
        boundary = param.split("=", 1)[1].strip().strip('"')
        return boundary
    return ""


async def _save_gallery_item(
    request: Request,
    db,
    current_user: dict | None,
    filename: str,
    media_type: str,
    file_data: bytes,
    result: dict,
) -> UploadGalleryItem:
    item_id = f"upload_{uuid4().hex}"
    bucket = AsyncIOMotorGridFSBucket(db)
    file_id = await bucket.upload_from_stream(
        filename,
        file_data,
        metadata={
            "galleryItemId": item_id,
            "contentType": media_type,
            "ownerId": current_user.get("id") if current_user else None,
        },
    )
    video_path = f"/api/analyze-clip/gallery/{item_id}/video"
    video_url = str(request.base_url).rstrip("/") + video_path
    file_info = {
        "name": filename,
        "type": media_type,
        "size": len(file_data),
    }
    document = {
        "id": item_id,
        "ownerId": current_user.get("id") if current_user else None,
        "ownerUsername": current_user.get("username") if current_user else None,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "filename": filename,
        "mimeType": media_type,
        "localPath": None,
        "videoFileId": str(file_id),
        "videoUrl": video_url,
        "provider": result["provider"],
        "summary": result["text"],
        "rawResponse": result.get("rawText"),
        "file": file_info,
        "event": result.get("event") or result.get("analysis"),
    }
    await db.upload_gallery.insert_one(document)
    document.pop("_id", None)
    return UploadGalleryItem(**document)


def _owner_query(current_user: dict | None) -> dict:
    if current_user is None:
        return {"ownerId": None}
    return {"ownerId": current_user["id"]}


def _range_bounds(range_header: str | None, file_size: int) -> tuple[int, int]:
    if not range_header or not range_header.startswith("bytes="):
        return 0, max(file_size - 1, 0)
    raw = range_header.removeprefix("bytes=").split(",", 1)[0].strip()
    start_text, _, end_text = raw.partition("-")
    try:
        if start_text:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
        else:
            suffix_length = int(end_text)
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
    except ValueError:
        return 0, max(file_size - 1, 0)
    start = min(max(start, 0), max(file_size - 1, 0))
    end = min(max(end, start), max(file_size - 1, 0))
    return start, end
