import base64
import hashlib
import hmac
import json
import re
import time

from app.config import settings


class MissingLiveKitConfigError(Exception):
    pass


class BadRequestError(Exception):
    pass


def create_livekit_token(room: str | None = None, identity: str | None = None) -> dict:
    if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
        raise MissingLiveKitConfigError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are required.")

    room_value = safe_token_value(room or "mochi-monitor-demo", "room")
    identity_value = safe_token_value(identity or f"owner-{int(time.time())}", "identity")
    now = int(time.time())
    claims = {
        "iss": settings.livekit_api_key,
        "sub": identity_value,
        "nbf": now - 10,
        "exp": now + 60 * 60,
        "video": {
            "room": room_value,
            "roomJoin": True,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
        },
    }
    return {
        "configured": True,
        "url": settings.livekit_url,
        "room": room_value,
        "identity": identity_value,
        "token": sign_jwt(claims, settings.livekit_api_secret),
    }


def safe_token_value(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text or len(text) > 80:
        raise BadRequestError(f"{field_name} must be 1-80 characters.")
    if not re.match(r"^[A-Za-z0-9_.:-]+$", text):
        raise BadRequestError(f"{field_name} may only contain letters, numbers, dash, underscore, dot, or colon.")
    return text


def sign_jwt(claims: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{b64url_json(header)}.{b64url_json(claims)}"
    signature = hmac.new(secret.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def b64url_json(value: dict) -> str:
    return b64url(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
