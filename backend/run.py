import atexit
import subprocess
import sys
from pathlib import Path

import uvicorn

from app.config import settings
from app.services.voice_worker import stop_voice_worker

ROOT = Path(__file__).resolve().parent
_voice_proc: subprocess.Popen | None = None


def _voice_enabled() -> bool:
    return bool(settings.start_voice_worker)


def _start_voice_worker() -> subprocess.Popen | None:
    if not _voice_enabled():
        return None
    if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
        print("Voice worker skipped: set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET.")
        return None

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "voice_agent.py"), "dev"],
        cwd=ROOT,
    )
    print(f"==> Voice worker started (PID {proc.pid}).")
    return proc


def _stop_voice_worker() -> None:
    global _voice_proc
    if _voice_proc is None or _voice_proc.poll() is not None:
        stop_voice_worker()
        return
    print("==> Stopping voice worker...")
    _voice_proc.terminate()
    try:
        _voice_proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        _voice_proc.kill()
        _voice_proc.wait()
    _voice_proc = None
    stop_voice_worker()


def main() -> None:
    global _voice_proc
    _voice_proc = _start_voice_worker()
    atexit.register(_stop_voice_worker)

    try:
        uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=True)
    finally:
        _stop_voice_worker()


if __name__ == "__main__":
    main()
