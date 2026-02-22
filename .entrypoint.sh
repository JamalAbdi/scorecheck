#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/src/backend"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  echo "Backend venv not found. Create it first:"
  echo "  cd src/backend"
  echo "  /bin/python3 -m venv .venv"
  echo "  . .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

echo "Starting FastAPI (auto-reload)..."
(
  cd "$BACKEND_DIR"
  . .venv/bin/activate
  uvicorn main:app --reload --port 8000
) &
BACKEND_PID=$!

echo "Starting Vue dev server (auto-reload)..."
(
  cd "$ROOT_DIR"
  npm run serve
) &
FRONTEND_PID=$!

echo "Both servers are running. Press Ctrl+C to stop."
wait