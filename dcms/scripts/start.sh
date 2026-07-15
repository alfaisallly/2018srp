#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== DCMS Quick Start (Linux/macOS) ==="

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

[ -f .env ] || cp .env.example .env

if command -v docker &>/dev/null; then
  docker compose up -d
  sleep 3
fi

python scripts/init_db.py
echo "Starting DCMS on http://localhost:8080"
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
