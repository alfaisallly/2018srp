from __future__ import annotations

"""Lightweight smoke checks for NetPulse core modules (no server required)."""

import asyncio
import sys
import tempfile
from pathlib import Path

# Allow running as: python backend/smoke_test.py
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Database
from app.monitor import MonitorEngine


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        database = Database(db_path)
        await database.connect()
        await database.seed_defaults()
        targets = await database.list_targets()
        assert len(targets) >= 4, "expected seeded targets"

        engine = MonitorEngine(database)
        loopback = next(t for t in targets if t["host"] == "127.0.0.1" and t["check_type"] == "ping")
        result = await engine.probe(loopback)
        assert result["status"] in {"up", "degraded", "down"}, result
        print("probe loopback:", result)

        created = await database.create_target(
            {
                "name": "Smoke TCP",
                "host": "127.0.0.1",
                "check_type": "tcp",
                "port": 9,  # discard — usually closed, still a valid probe path
                "tags": ["smoke"],
            }
        )
        tcp = await engine.probe(created)
        assert tcp["status"] in {"up", "down"}, tcp
        print("probe tcp:", tcp)

        overview = await database.overview()
        assert "counts" in overview and "targets" in overview
        print("overview counts:", overview["counts"])
        await database.close()
    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
