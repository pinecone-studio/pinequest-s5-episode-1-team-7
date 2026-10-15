#!/usr/bin/env bash
# One-click start (macOS / Linux): sets up and runs the backend + AI engine and the dashboard,
# then opens http://localhost:5173 in the browser. Press Ctrl+C to stop everything.
# On macOS you can double-click start.command instead. Windows: start.bat.
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

say "Checking Python 3.11+ and Node.js"
PY=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
     "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    PY=$candidate
    break
  fi
done
[ -n "$PY" ] || fail "Python 3.11 or newer is required: https://www.python.org/downloads/"
command -v npm >/dev/null 2>&1 || fail "Node.js 20 or newer is required: https://nodejs.org/"
echo "Using $("$PY" --version) and Node $(node --version)"

if curl -s -o /dev/null http://127.0.0.1:8000/docs; then
  fail "Something is already running on port 8000 (another backend?). Stop it and try again."
fi

say "Setting up the backend (first run takes a few minutes)"
[ -x backend/.venv/bin/python ] || "$PY" -m venv backend/.venv
backend/.venv/bin/python -m pip install --quiet --disable-pip-version-check -r backend/requirements.txt

[ -f engine/model/model_fp32.onnx ] ||
  echo "WARNING: engine/model/model_fp32.onnx is missing; every slide will fail until it is there."

say "Setting up the dashboard"
if [ ! -d frontend/node_modules ] || [ ! -f frontend/node_modules/.package-lock.json ] || [ frontend/package-lock.json -nt frontend/node_modules/.package-lock.json ]; then
  echo "Installing updated dashboard packages (this takes a few minutes on first run)..."
  (cd frontend && npm ci --no-audit --no-fund)
fi

say "Starting the backend on http://127.0.0.1:8000"
(cd backend && exec .venv/bin/python run_server.py) &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT INT TERM

for _ in $(seq 1 120); do
  curl -s -o /dev/null http://127.0.0.1:8000/docs && break
  kill -0 "$BACKEND_PID" 2>/dev/null || fail "The backend stopped while starting; see the messages above."
  sleep 1
done
curl -s -o /dev/null http://127.0.0.1:8000/docs || fail "The backend did not start within 2 minutes."

say "Starting the dashboard on http://localhost:5173 (Ctrl+C to stop)"
cd frontend
npm run dev -- --open
