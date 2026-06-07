import re
import secrets
from datetime import date, datetime, timezone

ACCENTS = ["#66d19e", "#e4bd5b", "#76c7d8", "#ef7c73", "#d3c7a3"]


class CatError(Exception):
    pass


def create_cat_id() -> str:
    return f"cat_{secrets.token_hex(8)}"


def cat_initials(name: str) -> str:
    parts = [part for part in re.split(r"\s+", name.strip()) if part]
    if not parts:
        return "??"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[1][0]}".upper()


def parse_birth_date(value: str) -> date:
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as error:
        raise CatError("Birth date must use YYYY-MM-DD format.") from error
    if parsed > date.today():
        raise CatError("Birth date cannot be in the future.")
    return parsed


def format_age(birth_date: date) -> str:
    today = date.today()
    total_months = (today.year - birth_date.year) * 12 + (today.month - birth_date.month)
    if today.day < birth_date.day:
        total_months -= 1
    total_months = max(total_months, 0)
    if total_months < 12:
        return "1 mo" if total_months == 1 else f"{total_months} mo"
    years = total_months // 12
    return "1 yr" if years == 1 else f"{years} yrs"


def validate_name(name: str) -> str:
    value = name.strip()
    if not value or len(value) > 40:
        raise CatError("Name must be 1-40 characters.")
    return value


def validate_device(device: str | None) -> str | None:
    if device is None:
        return None
    value = device.strip()
    if not value:
        return None
    if len(value) > 80:
        raise CatError("Device name must be 80 characters or fewer.")
    return value


def pick_accent(existing_count: int) -> str:
    return ACCENTS[existing_count % len(ACCENTS)]


def build_cat_document(
    owner_id: str,
    owner_username: str,
    name: str,
    birth_date: date,
    device: str | None,
    existing_count: int,
) -> dict:
    return {
        "id": create_cat_id(),
        "owner_id": owner_id,
        "owner_username": owner_username,
        "name": name,
        "birth_date": birth_date.isoformat(),
        "device": device,
        "initials": cat_initials(name),
        "accent": pick_accent(existing_count),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def build_cat_update(name: str, birth_date: date, device: str | None) -> dict:
    return {
        "name": name,
        "birth_date": birth_date.isoformat(),
        "device": device,
        "initials": cat_initials(name),
    }


def public_cat(cat: dict) -> dict:
    birth = parse_birth_date(cat["birth_date"])
    return {
        "id": cat["id"],
        "ownerId": cat.get("owner_id"),
        "ownerUsername": cat.get("owner_username"),
        "name": cat["name"],
        "initials": cat.get("initials") or cat_initials(cat["name"]),
        "age": format_age(birth),
        "birthDate": cat["birth_date"],
        "device": cat.get("device"),
        "accent": cat.get("accent") or ACCENTS[0],
    }
