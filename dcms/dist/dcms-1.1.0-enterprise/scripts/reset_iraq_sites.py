"""Remove legacy Riyadh demo data and ensure Iraqi datacenters exist."""

import asyncio
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("init_db", ROOT / "scripts" / "init_db.py")
init_db = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(init_db)


if __name__ == "__main__":
    asyncio.run(init_db.init_db())
    print("Iraqi datacenters ready. Legacy Riyadh data removed.")
