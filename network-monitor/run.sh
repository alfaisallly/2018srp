#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.venv"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtualenv at $VENV"
  "$PYTHON" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install -q --upgrade pip
pip install -q -r backend/requirements.txt

export PYTHONPATH="$ROOT/backend:${PYTHONPATH:-}"

echo "Starting NetPulse on http://${HOST}:${PORT}"
exec python -m uvicorn app.main:app --host "$HOST" --port "$PORT" --app-dir "$ROOT/backend"
