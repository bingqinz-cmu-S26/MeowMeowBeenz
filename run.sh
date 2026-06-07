#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PID=""
VOICE_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo ""
    echo "Stopping backend (PID $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$VOICE_PID" ]] && kill -0 "$VOICE_PID" 2>/dev/null; then
    echo "Stopping voice worker (PID $VOICE_PID)..."
    kill "$VOICE_PID" 2>/dev/null || true
    wait "$VOICE_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

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

LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [[ -z "$LOCAL_IP" ]]; then
  LOCAL_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi
if [[ -n "$LOCAL_IP" ]]; then
  API_URL="${API_URL:-http://${LOCAL_IP}:8000}"
else
  API_URL="${API_URL:-http://localhost:8000}"
fi

if lsof -ti :8000 >/dev/null 2>&1; then
  echo "==> Freeing port 8000..."
  lsof -ti :8000 | xargs kill 2>/dev/null || true
  sleep 1
fi

echo "==> Starting backend (http://localhost:8000)..."
(
  cd backend
  exec .venv/bin/python run.py
) &
BACKEND_PID=$!

echo -n "==> Waiting for backend"
for _ in $(seq 1 40); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    echo " ready."
    break
  fi
  echo -n "."
  sleep 0.25
done

if ! curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
  echo ""
  echo "Error: backend did not start. Check backend logs above."
  exit 1
fi

echo "==> API URL: $API_URL"
echo "==> Backend is running on http://localhost:8000 (Ctrl+C stops it)"
echo ""

if [[ -f .env ]] && grep -qE '^LIVEKIT_URL=.+' .env && [[ "${START_VOICE_WORKER:-1}" != "0" ]]; then
  echo "==> Installing voice requirements (backend/requirements-voice.txt)..."
  backend/.venv/bin/pip install -q -r backend/requirements-voice.txt

  echo "==> Starting voice worker (dev)..."
  (
    cd backend
    exec .venv/bin/python voice_agent.py dev
  ) &
  VOICE_PID=$!
  echo "==> Voice worker running (set START_VOICE_WORKER=0 to skip)"
  echo ""
elif [[ "${START_VOICE_WORKER:-0}" == "1" || "${START_VOICE_WORKER:-false}" == "true" ]]; then
  echo "==> Installing voice requirements (backend/requirements-voice.txt)..."
  backend/.venv/bin/pip install -q -r backend/requirements-voice.txt

  echo "==> Starting voice worker (dev)..."
  (
    cd backend
    exec .venv/bin/python voice_agent.py dev
  ) &
  VOICE_PID=$!
fi

wait
