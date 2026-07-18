#!/usr/bin/env bash
set -euo pipefail
cd /app
export PYTHONPATH=/app
echo "Waiting for database..."
sleep 5
python scripts/init_db.py || echo "init_db skipped or already done"
exec "$@"
