#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "==> MeowMeowBeenz"

if [[ ! -f .env ]]; then
  echo "Error: .env not found. Run: cp .env.example .env"
  exit 1
fi

if [[ ! -d backend/.venv ]]; then
  echo "==> Creating Python virtualenv..."
  python3 -m venv backend/.venv
fi

echo "==> Installing backend dependencies..."
backend/.venv/bin/pip install -q -r backend/requirements.txt

if grep -qE '^LIVEKIT_URL=.+' .env && [[ "${START_VOICE_WORKER:-1}" != "0" ]]; then
  echo "==> Installing voice dependencies..."
  backend/.venv/bin/pip install -q -r backend/requirements-voice.txt
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

echo "==> Starting backend (+ voice worker when LIVEKIT_* is set)..."
cd backend
exec .venv/bin/python run.py
