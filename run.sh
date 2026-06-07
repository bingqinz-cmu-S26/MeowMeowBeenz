#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo ""
    echo "Stopping backend (PID $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
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

if [[ ! -d mobile/node_modules ]]; then
  echo "==> Installing mobile dependencies..."
  (cd mobile && npm install)
fi

LOCAL_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
if [[ -z "$LOCAL_IP" ]]; then
  LOCAL_IP="$(ipconfig getifaddr en1 2>/dev/null || true)"
fi
if [[ -n "$LOCAL_IP" ]]; then
  export EXPO_PUBLIC_API_URL="${EXPO_PUBLIC_API_URL:-http://${LOCAL_IP}:8000}"
else
  export EXPO_PUBLIC_API_URL="${EXPO_PUBLIC_API_URL:-http://localhost:8000}"
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

echo "==> Mobile API URL: $EXPO_PUBLIC_API_URL"
echo "==> Starting Expo (Ctrl+C stops everything)"
echo ""

cd mobile
exec npm start
