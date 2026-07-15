from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.datacenters import router as datacenters_router
from app.api.devices import router as devices_router
from app.api.network_maps import router as network_maps_router
from app.api.reports import router as reports_router
from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.models import Base
from app.services.device_monitor import poll_all_devices

settings = get_settings()
scheduler = AsyncIOScheduler()


async def scheduled_poll():
    async with AsyncSessionLocal() as session:
        try:
            await poll_all_devices(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scheduler.add_job(scheduled_poll, "interval", seconds=settings.poll_interval_seconds, id="device_poll")
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
app.include_router(datacenters_router, prefix=api_prefix)
app.include_router(devices_router, prefix=api_prefix)
app.include_router(network_maps_router, prefix=api_prefix)
app.include_router(alerts_router, prefix=api_prefix)
app.include_router(reports_router, prefix=api_prefix)

_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/static", StaticFiles(directory=_frontend_dir / "static"), name="static")
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
