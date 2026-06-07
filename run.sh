#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> MeowMeowBeenz"

if [[ ! -f .env ]]; then
  echo "Error: .env not found. Run: cp .env.example .env"
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3.12 || command -v python3)"
fi

if ! "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo "Error: Python 3.10+ is required for the backend. Set PYTHON_BIN=/path/to/python3.12"
  exit 1
fi

if [[ ! -d .venv-backend ]]; then
  echo "==> Creating Python virtualenv..."
  "$PYTHON_BIN" -m venv .venv-backend
fi

echo "==> Installing backend dependencies..."
.venv-backend/bin/pip install -q -r backend/requirements.txt

if grep -qE '^LIVEKIT_URL=.+' .env; then
  echo "==> Installing voice dependencies..."
  .venv-backend/bin/pip install -q -r backend/requirements-voice.txt
fi

if lsof -ti :8000 >/dev/null 2>&1; then
  echo "==> Freeing port 8000..."
  lsof -ti :8000 | xargs kill 2>/dev/null || true
  sleep 1
fi

LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [[ -z "$LOCAL_IP" ]]; then
  LOCAL_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi
if [[ -n "$LOCAL_IP" ]]; then
  echo "==> API URL: http://${LOCAL_IP}:8000"
else
  echo "==> API URL: http://localhost:8000"
fi

echo "==> Starting backend..."
cd backend
exec ../.venv-backend/bin/python run.py
