"""Process helper for the LiveKit voice worker."""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from subprocess import Popen
from time import perf_counter

from app.config import settings
from app.services.livekit import MissingLiveKitConfigError


_LOCK = threading.Lock()
_worker_proc: Popen | None = None
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _worker_is_running() -> bool:
    global _worker_proc
    return _worker_proc is not None and _worker_proc.poll() is None


def start_voice_worker() -> bool:
    """Start the LiveKit worker if it is not already running."""
    global _worker_proc
    if _worker_is_running():
        return True

    if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
        raise MissingLiveKitConfigError("LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are required.")

    with _LOCK:
        if _worker_is_running():
            return True

        _worker_proc = subprocess.Popen(
            [sys.executable, str(_BACKEND_ROOT / "voice_agent.py"), "dev"],
            cwd=_BACKEND_ROOT,
        )
        print("==> Starting LiveKit voice worker on-demand for this session.")
        return True


def ensure_voice_worker_on_demand() -> None:
    """Start the worker only when requested by the voice-chat flow."""
    if settings.start_voice_worker:
        # Managed by run.py startup in this mode; avoid spawning a duplicate.
        return

    if _worker_is_running():
        return
    start_voice_worker()


def stop_voice_worker() -> bool:
    global _worker_proc
    with _LOCK:
        proc = _worker_proc
        if proc is None:
            return False

        if proc.poll() is not None:
            _worker_proc = None
            return False

    started_at = perf_counter()
    try:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    except ProcessLookupError:
        pass
    finally:
        _worker_proc = None

    stopped_ms = round((perf_counter() - started_at) * 1000)
    print(f"==> Stopped LiveKit voice worker in {stopped_ms}ms.")
    return True
