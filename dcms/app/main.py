from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.users import router as users_router
from app.api.servers import router as servers_router
from app.api.storage import router as storage_router
from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.datacenters import router as datacenters_router
from app.api.devices import router as devices_router
from app.api.network_maps import router as network_maps_router
from app.api.reports import router as reports_router
from app.api.import_data import router as import_router
from app.api.sensors import router as sensors_router
from app.api.ipam import router as ipam_router
from app.api.backups import router as backups_router
from app.api.integrations import router as integrations_router
from app.api.capabilities import router as capabilities_router
from app.api.network_control import router as network_control_router
from sqlalchemy import text

from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.models import Base
from app.services.device_monitor import poll_all_devices
from app.services.server_monitor import poll_all_servers
from app.services.storage_monitor import poll_all_storage
from app.services.sensor_engine import seed_all_sensors
from app.services.config_backup import backup_all_eligible
from app.services.integration_sync import sync_all_integrations

settings = get_settings()
scheduler = AsyncIOScheduler()


async def scheduled_poll():
    async with AsyncSessionLocal() as session:
        try:
            await poll_all_devices(session)
            await poll_all_servers(session)
            await poll_all_storage(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def scheduled_config_backup():
    async with AsyncSessionLocal() as session:
        try:
            await backup_all_eligible(session)
            await session.commit()
        except Exception:
            await session.rollback()


async def scheduled_integration_sync():
    async with AsyncSessionLocal() as session:
        try:
            await sync_all_integrations(session)
            await session.commit()
        except Exception:
            await session.rollback()


async def _migrate_enums(conn):
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS permissions JSONB",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS server_id INTEGER",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS storage_id INTEGER",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS sensor_id INTEGER",
    ]
    for stmt in migrations:
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass
    for val in ("ipmi", "winrm"):
        try:
            await conn.execute(text(f"ALTER TYPE protocoltype ADD VALUE IF NOT EXISTS '{val}'"))
        except Exception:
            pass
    try:
        await conn.execute(text("CREATE TYPE devicetype AS ENUM ('switch', 'firewall', 'router', 'other')"))
    except Exception:
        pass
    try:
        await conn.execute(text("ALTER TABLE devices ADD COLUMN IF NOT EXISTS device_type devicetype DEFAULT 'switch'"))
        await conn.execute(text("UPDATE devices SET device_type = 'firewall' WHERE vendor = 'FORTINET'"))
        await conn.execute(text("UPDATE devices SET device_type = 'switch' WHERE device_type IS NULL"))
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_enums(conn)

    async with AsyncSessionLocal() as session:
        try:
            await seed_all_sensors(session)
            await session.commit()
        except Exception:
            await session.rollback()

    scheduler.add_job(scheduled_poll, "interval", seconds=settings.poll_interval_seconds, id="device_poll")
    scheduler.add_job(scheduled_config_backup, "cron", hour=2, minute=0, id="config_backup")
    scheduler.add_job(scheduled_integration_sync, "interval", hours=1, id="integration_sync")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="نظام متكامل لإدارة مراكز البيانات - DCMS",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"
app.include_router(auth_router, prefix=api_prefix)
app.include_router(users_router, prefix=api_prefix)
app.include_router(datacenters_router, prefix=api_prefix)
app.include_router(devices_router, prefix=api_prefix)
app.include_router(servers_router, prefix=api_prefix)
app.include_router(storage_router, prefix=api_prefix)
app.include_router(network_maps_router, prefix=api_prefix)
app.include_router(alerts_router, prefix=api_prefix)
app.include_router(reports_router, prefix=api_prefix)
app.include_router(import_router, prefix=api_prefix)
app.include_router(sensors_router, prefix=api_prefix)
app.include_router(ipam_router, prefix=api_prefix)
app.include_router(backups_router, prefix=api_prefix)
app.include_router(integrations_router, prefix=api_prefix)
app.include_router(capabilities_router, prefix=api_prefix)
app.include_router(network_control_router, prefix=api_prefix)

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/static", StaticFiles(directory=_frontend_dir / "static"), name="static")
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
