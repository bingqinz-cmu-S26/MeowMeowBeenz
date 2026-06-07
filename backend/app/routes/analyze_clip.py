from email.message import Message
from email.parser import BytesParser
from email.policy import default

from fastapi import APIRouter, HTTPException, Request

from app.database import get_database
from app.models.schemas import ClipAnalysisResponse, ClipFileInfo
from app.services.video_analysis import analyze_video_clip

router = APIRouter(prefix="/api/analyze-clip", tags=["analyze-clip"])


@router.post("")
async def analyze_clip(request: Request) -> ClipAnalysisResponse:
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
    if db is not None and isinstance(event, dict):
        await db.events.insert_one(event)

    return ClipAnalysisResponse(
        ok=True,
        provider=result["provider"],
        text=result["text"],
        file=ClipFileInfo(
            name=filename,
            type=media_type,
            size=len(file_data),
        ),
        event=result.get("event"),
        analysis=result.get("analysis"),
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
