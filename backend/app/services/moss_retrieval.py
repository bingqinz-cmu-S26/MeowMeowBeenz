"""Moss-backed retrieval adapter for timeline lookup."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import asyncio
import json
import logging
from time import perf_counter

from app.config import settings
from app.services.cat_timeline import all_events, parse_timestamp

logger = logging.getLogger("cat-moss-retrieval")

_client: object | None = None
_client_lock = asyncio.Lock()
_sdk_available: bool = True
_index_ready: bool = False


def _format_score(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_event_map(value: object) -> dict | None:
    try:
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "__dict__") and value.__dict__:
            return value.__dict__
        # Moss SDK QueryResultDocumentInfo exposes fields as read-only attributes.
        attr_keys = ("id", "text", "metadata", "score", "index_name")
        if any(hasattr(value, key) for key in attr_keys):
            return {key: getattr(value, key) for key in attr_keys if hasattr(value, key)}
        return None
    except TypeError:
        return {}


def _coerce_metadata_text(candidate: object) -> str:
    if candidate is None:
        return ""
    if isinstance(candidate, str):
        return candidate
    try:
        return json.dumps(candidate, ensure_ascii=False)
    except TypeError:
        return str(candidate)


def _to_str_metadata(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, str] = {}
    for key, raw in value.items():
        out[str(key)] = "" if raw is None else str(raw)
    return out


def _build_seed_documents() -> list[object]:
    from moss import DocumentInfo

    docs: list[object] = []
    for idx, event in enumerate(all_events()):
        cat_id = str(event.get("catId") or "")
        cat_name = str(event.get("catName") or "")
        action = str(event.get("action") or "")
        description = str(event.get("description") or "")
        mood = str(event.get("mood") or "")
        mood_label = str(event.get("moodLabel") or "")
        mood_summary = str(event.get("moodSummary") or "")
        timestamp = str(event.get("timestamp") or "")
        confidence = str(event.get("confidence") if event.get("confidence") is not None else "")
        search_text = " ".join(part for part in [cat_name, mood_label, action, description] if part).strip()
        if not search_text:
            search_text = f"{cat_name}: {action}"

        metadata = _to_str_metadata(
            {
                "catId": cat_id,
                "catName": cat_name,
                "mood": mood,
                "moodLabel": mood_label,
                "moodSummary": mood_summary,
                "timestamp": timestamp,
                "description": description,
                "confidence": confidence,
                "source": "mockData",
                "retrieval_source": "mockData",
            }
        )
        docs.append(
            DocumentInfo(
                id=f"{cat_id}:{timestamp}:{idx}",
                text=search_text,
                metadata=metadata,
            )
        )
    return docs


async def _load_local_index(client: object, index_name: str) -> bool:
    try:
        await client.load_index(index_name)
        logger.debug("Moss index '%s' loaded locally.", index_name)
        return True
    except Exception as exc:
        logger.debug("Moss index '%s' is not loaded locally yet (%s).", index_name, exc)
        return False


async def _seed_cloud_index(client: object, index_name: str) -> bool:
    try:
        from moss import MutationOptions
    except Exception:
        logger.debug("Moss MutationOptions unavailable; skipping automatic index bootstrap.")
        return False

    docs = _build_seed_documents()
    if not docs:
        return True

    try:
        try:
            await client.create_index(index_name, docs)
            logger.debug("Created Moss index '%s' from data/mockData.json.", index_name)
        except Exception as exc:
            logger.debug("create_index failed for '%s' (%s); continuing with upsert.", index_name, exc)

        await client.add_docs(index_name, docs, MutationOptions(upsert=True))
        logger.debug("Upserted mockData docs into Moss index '%s'.", index_name)
        return True
    except Exception as exc:
        logger.warning("Moss auto-seed failed for '%s': %s", index_name, exc)
        return False


async def _ensure_local_index(client: object) -> bool:
    """Load the Moss index into memory so query() runs locally, not via cloud API."""
    global _index_ready
    if _index_ready:
        return True

    index_name = settings.moss_index_name
    if not index_name:
        return False

    if await _load_local_index(client, index_name):
        _index_ready = True
        return True

    if not settings.moss_auto_seed_index:
        return False

    if not await _seed_cloud_index(client, index_name):
        return False

    if await _load_local_index(client, index_name):
        _index_ready = True
        return True

    logger.warning("Moss index '%s' was seeded but could not be loaded locally.", index_name)
    return False


def _normalize_doc(doc: object) -> dict:
    payload = _to_event_map(doc) or {}
    raw_metadata = payload.get("metadata")
    metadata = _to_event_map(raw_metadata) or {}
    if not metadata:
        metadata = _to_event_map(_coerce_metadata_text(raw_metadata)) or {}

    text = str(payload.get("text", "") or "")
    if not text:
        text = str(metadata.get("content") or "")

    when_raw = metadata.get("timestamp") or metadata.get("time") or metadata.get("when") or metadata.get("recorded_at")
    when = None
    try:
        if isinstance(when_raw, datetime):
            when = when_raw
        elif isinstance(when_raw, str):
            when = parse_timestamp(when_raw)
        elif when_raw is not None:
            when = datetime.fromisoformat(str(when_raw))
    except (ValueError, TypeError):
        when = None

    if not metadata and text and ": " in text:
        left, right = text.split(": ", 1)
        if left and right:
            metadata.setdefault("catName", left.strip())
            metadata.setdefault("action", right.strip())

    action = str(
        metadata.get("action")
        or metadata.get("event")
        or metadata.get("summary")
        or (text.split("- ", 1)[1].strip() if "- " in text else text)
    )

    cat_name = str(metadata.get("catName") or metadata.get("cat") or "")
    cat_id = str(metadata.get("catId") or metadata.get("cat_id") or cat_name)
    mood = str(metadata.get("mood") or "content")
    mood_label = str(metadata.get("moodLabel") or metadata.get("mood_label") or metadata.get("moodSummary") or mood)
    mood_summary = str(metadata.get("moodSummary") or metadata.get("summary") or "")
    description = str(metadata.get("description") or metadata.get("note") or text or "")

    try:
        confidence = float(metadata.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    source = str(metadata.get("source", "") or metadata.get("retrieval_source", "") or "unknown")
    source = source.strip() or "unknown"

    return {
        "catId": cat_id,
        "catName": cat_name,
        "mood": mood,
        "moodLabel": mood_label,
        "moodSummary": mood_summary,
        "action": action,
        "timestamp": metadata.get("timestamp", ""),
        "when": when,
        "confidence": confidence,
        "description": description,
        "score": round(_format_score(payload.get("score", 0.0)), 3),
        "source": "moss",
        "retrieval_source": source,
    }


def _is_mock_data_event(event: dict) -> bool:
    return str(event.get("retrieval_source", "")).strip().lower() == "mockdata"


def _cat_matches(event: dict, cat_id: str | None) -> bool:
    if not cat_id:
        return True
    return str(event.get("catId", "")).lower() == str(cat_id).lower()


def _within_window(event: dict, window: tuple[datetime, datetime] | None) -> bool:
    if not window:
        return True
    when = event.get("when")
    if not isinstance(when, datetime):
        return False
    start, end = window
    return start <= when <= end


def _resolve_limit(limit: int | None) -> int:
    base = int(limit) if limit else settings.moss_top_k
    if base <= 0:
        return int(settings.moss_top_k) if int(settings.moss_top_k) > 0 else 6
    return base


async def preload_moss_index() -> bool:
    """Warm the Moss index once per process so queries skip cold load_index."""
    if not settings.moss_enabled:
        return False

    global _sdk_available
    if not _sdk_available:
        return False

    if _index_ready:
        return True

    started = perf_counter()
    try:
        async with _client_lock:
            global _client
            if _client is None:
                _client = await _build_client()
            ready = await _ensure_local_index(_client)
    except Exception as exc:
        logger.warning("Moss preload failed: %s", exc)
        return False

    if ready:
        logger.info(
            "Moss index '%s' preloaded in %.0fms.",
            settings.moss_index_name,
            (perf_counter() - started) * 1000,
        )
    return ready


async def _build_client() -> object:
    try:
        from moss import MossClient
    except ModuleNotFoundError as exc:
        raise RuntimeError("Moss SDK is not installed.") from exc

    return MossClient(
        settings.moss_project_id,
        settings.moss_project_key,
    )


async def query_moss(
    question: str,
    cat_id: str | None = None,
    window: tuple[datetime, datetime] | None = None,
    limit: int | None = None,
) -> list[dict]:
    if not settings.moss_enabled:
        return []

    global _sdk_available
    if not _sdk_available:
        return []

    resolved_limit = _resolve_limit(limit)

    try:
        from moss import QueryOptions
    except Exception as exc:
        logger.warning("Moss SDK import failed. Install with `pip install moss`.")
        logger.debug("Moss import error: %s", exc)
        _sdk_available = False
        return []

    try:
        async with _client_lock:
            global _client
            if _client is None:
                _client = await _build_client()
            client = _client

            if not await _ensure_local_index(client):
                return []

        query_opts = QueryOptions(top_k=resolved_limit, alpha=float(settings.moss_alpha))
        result = await asyncio.wait_for(
            client.query(settings.moss_index_name, question, query_opts),
            timeout=float(settings.moss_query_timeout_seconds),
        )

        if isinstance(result, Mapping):
            raw_docs = result.get("docs", [])
        else:
            raw_docs = getattr(result, "docs", [])

        docs: list[dict] = []
        for doc in raw_docs:
            event = _normalize_doc(doc)
            if not _is_mock_data_event(event):
                continue
            if not _cat_matches(event, cat_id):
                continue
            if not _within_window(event, window):
                continue
            docs.append(event)

        docs.sort(key=lambda event: event.get("score", 0.0), reverse=True)
        return docs[:resolved_limit]

    except asyncio.TimeoutError:
        logger.warning("Moss query timed out after %.2fs", float(settings.moss_query_timeout_seconds))
        return []
    except Exception as exc:
        logger.warning("Moss query failed: %s", exc)
        return []
