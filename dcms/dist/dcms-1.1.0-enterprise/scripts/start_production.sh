#!/usr/bin/env bash
# Start DCMS in production mode (no reload)
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-.}"
source venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port "${DCMS_PORT:-8080}" --workers "${DCMS_WORKERS:-2}"
