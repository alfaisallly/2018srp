from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import db
from .monitor import MonitorEngine, discover_local_hosts
from .schemas import DiscoverRequest, TargetCreate, TargetUpdate

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"

monitor = MonitorEngine(db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    await db.seed_defaults()
    await monitor.start()
    # Warm first sweep so the dashboard is not empty.
    await monitor.check_now()
    yield
    await monitor.stop()
    await db.close()


app = FastAPI(
    title=settings.app_name,
    description="End-to-end network monitoring: inventory, probes, history, and alerts.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/overview")
async def overview() -> dict[str, Any]:
    return await db.overview()


@app.get("/api/targets")
async def list_targets() -> list[dict[str, Any]]:
    overview_data = await db.overview()
    return overview_data["targets"]


@app.post("/api/targets", status_code=201)
async def create_target(payload: TargetCreate) -> dict[str, Any]:
    if payload.check_type == "tcp" and payload.port is None:
        raise HTTPException(status_code=400, detail="TCP checks require a port")
    created = await db.create_target(payload.model_dump())
    await monitor.check_now(created["id"])
    latest = await db.latest_check(created["id"])
    return {**created, "latest": latest, "status": latest["status"] if latest else "unknown"}


@app.get("/api/targets/{target_id}")
async def get_target(target_id: int) -> dict[str, Any]:
    target = await db.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    latest = await db.latest_check(target_id)
    history = await db.check_history(target_id, limit=60)
    return {
        **target,
        "latest": latest,
        "status": latest["status"] if latest else "unknown",
        "history": list(reversed(history)),
    }


@app.patch("/api/targets/{target_id}")
async def update_target(target_id: int, payload: TargetUpdate) -> dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated = await db.update_target(target_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Target not found")
    if updated["enabled"]:
        await monitor.check_now(target_id)
    latest = await db.latest_check(target_id)
    return {**updated, "latest": latest, "status": latest["status"] if latest else "unknown"}


@app.delete("/api/targets/{target_id}")
async def delete_target(target_id: int) -> dict[str, str]:
    ok = await db.delete_target(target_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Target not found")
    return {"status": "deleted"}


@app.post("/api/targets/{target_id}/check")
async def check_target(target_id: int) -> dict[str, Any]:
    target = await db.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    results = await monitor.check_now(target_id)
    return results[0] if results else {"status": "unknown"}


@app.post("/api/checks/run")
async def run_all_checks() -> dict[str, Any]:
    results = await monitor.check_now()
    return {"checked": len(results), "results": results}


@app.get("/api/targets/{target_id}/history")
async def target_history(
    target_id: int,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    target = await db.get_target(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    history = await db.check_history(target_id, limit=limit)
    return list(reversed(history))


@app.get("/api/alerts")
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    unacked_only: bool = False,
) -> list[dict[str, Any]]:
    return await db.list_alerts(limit=limit, unacked_only=unacked_only)


@app.post("/api/alerts/{alert_id}/ack")
async def ack_alert(alert_id: int) -> dict[str, str]:
    ok = await db.acknowledge_alert(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "acknowledged"}


@app.get("/api/discover")
async def discover() -> dict[str, Any]:
    hosts = discover_local_hosts()
    return {"hosts": hosts, "count": len(hosts)}


@app.post("/api/discover/import")
async def discover_and_import(payload: DiscoverRequest) -> dict[str, Any]:
    hosts = discover_local_hosts()
    existing = {t["host"] for t in await db.list_targets()}
    imported = []
    for item in hosts:
        if item["host"] in existing:
            continue
        created = await db.create_target(
            {
                "name": item["name"],
                "host": item["host"],
                "check_type": "ping" if payload.import_as_ping else "ping",
                "tags": ["discovered"],
                "notes": "Imported by local discovery",
            }
        )
        imported.append(created)
        await monitor.check_now(created["id"])
    return {"imported": len(imported), "targets": imported}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
