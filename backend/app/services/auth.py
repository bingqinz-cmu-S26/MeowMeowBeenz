import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


class AuthError(Exception):
    pass


class DatabaseRequiredError(Exception):
    pass


def require_database(db):
    if db is None:
        raise DatabaseRequiredError("MongoDB is required for authentication.")


def normalize_username(username: str) -> str:
    value = username.strip()
    if not USERNAME_PATTERN.match(value):
        raise AuthError("Username must be 3-32 characters and use letters, numbers, or underscore.")
    return value


def validate_password(password: str) -> None:
    if len(password) < 6:
        raise AuthError("Password must be at least 6 characters.")
    if len(password) > 128:
        raise AuthError("Password must be 128 characters or fewer.")


def hash_password(password: str) -> str:
    validate_password(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user_id() -> str:
    return f"usr_{secrets.token_hex(8)}"


def create_access_token(user_id: str, username: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except JWTError as error:
        raise AuthError("Invalid or expired token.") from error


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "displayName": user.get("display_name") or user["username"],
        "createdAt": user.get("created_at"),
    }
