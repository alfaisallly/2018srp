from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_permission
from app.database import get_db
from app.models import Device, Permission, Sensor, SensorAssetType, SensorStatus, Server, StorageSystem, User
from app.schemas import (
    SensorHistoryPoint,
    SensorResponse,
    SensorSummary,
    SensorTemplatesResponse,
    SensorUpdate,
)
from app.services.sensor_engine import (
    DEFAULT_SENSOR_TEMPLATES,
    SENSOR_STATUS_COLORS,
    SENSOR_STATUS_LABELS,
    get_sensor_history,
    get_sensor_summary,
    seed_all_sensors,
)

router = APIRouter(prefix="/sensors", tags=["Sensors"])


def _enrich_sensor(sensor: Sensor, asset_name: str | None = None) -> SensorResponse:
    return SensorResponse(
        id=sensor.id,
        datacenter_id=sensor.datacenter_id,
        asset_type=sensor.asset_type,
        asset_id=sensor.device_id or sensor.server_id or sensor.storage_id or 0,
        asset_name=asset_name,
        device_id=sensor.device_id,
        server_id=sensor.server_id,
        storage_id=sensor.storage_id,
        name=sensor.name,
        metric_key=sensor.metric_key,
        unit=sensor.unit,
        warning_limit=sensor.warning_limit,
        error_limit=sensor.error_limit,
        higher_is_worse=sensor.higher_is_worse,
        enabled=sensor.enabled,
        last_value=sensor.last_value,
        last_status=sensor.last_status.value,
        last_message=sensor.last_message,
        last_check_at=sensor.last_check_at,
        status_color=SENSOR_STATUS_COLORS.get(sensor.last_status, "#64748b"),
        status_label=SENSOR_STATUS_LABELS.get(sensor.last_status, sensor.last_status.value),
        created_at=sensor.created_at,
    )


async def _asset_names(db: AsyncSession) -> dict[tuple[str, int], str]:
    names: dict[tuple[str, int], str] = {}
    for model, key in ((Device, "device"), (Server, "server"), (StorageSystem, "storage")):
        result = await db.execute(select(model))
        for row in result.scalars().all():
            names[(key, row.id)] = row.name
    return names


@router.get("", response_model=list[SensorResponse])
async def list_sensors(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
    asset_type: SensorAssetType | None = None,
    status_filter: str | None = None,
):
    query = select(Sensor).order_by(Sensor.datacenter_id, Sensor.asset_type, Sensor.name)
    if datacenter_id:
        query = query.where(Sensor.datacenter_id == datacenter_id)
    if asset_type:
        query = query.where(Sensor.asset_type == asset_type)
    if status_filter:
        try:
            query = query.where(Sensor.last_status == SensorStatus(status_filter))
        except ValueError:
            pass
    result = await db.execute(query)
    sensors = list(result.scalars().all())
    names = await _asset_names(db)
    return [
        _enrich_sensor(s, names.get((s.asset_type.value, s.device_id or s.server_id or s.storage_id or 0)))
        for s in sensors
    ]


@router.get("/summary", response_model=SensorSummary)
async def sensor_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    data = await get_sensor_summary(db, datacenter_id)
    return SensorSummary(**data)


@router.get("/templates", response_model=SensorTemplatesResponse)
async def sensor_templates(
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    templates = {
        key: {
            "name": tpl.name,
            "unit": tpl.unit,
            "warning": tpl.warning,
            "error": tpl.error,
            "higher_is_worse": tpl.higher_is_worse,
        }
        for key, tpl in DEFAULT_SENSOR_TEMPLATES.items()
    }
    return SensorTemplatesResponse(templates=templates, status_colors=SENSOR_STATUS_COLORS)


@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_sensors(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    return await seed_all_sensors(db)


@router.get("/{sensor_id}", response_model=SensorResponse)
async def get_sensor(
    sensor_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    sensor = await db.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    names = await _asset_names(db)
    asset_id = sensor.device_id or sensor.server_id or sensor.storage_id or 0
    return _enrich_sensor(sensor, names.get((sensor.asset_type.value, asset_id)))


@router.patch("/{sensor_id}", response_model=SensorResponse)
async def update_sensor(
    sensor_id: int,
    payload: SensorUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    sensor = await db.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")

    for field in ("name", "warning_limit", "error_limit", "higher_is_worse", "enabled", "unit"):
        value = getattr(payload, field)
        if value is not None:
            setattr(sensor, field, value)

    await db.flush()
    names = await _asset_names(db)
    asset_id = sensor.device_id or sensor.server_id or sensor.storage_id or 0
    return _enrich_sensor(sensor, names.get((sensor.asset_type.value, asset_id)))


@router.get("/{sensor_id}/history", response_model=list[SensorHistoryPoint])
async def sensor_history(
    sensor_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    limit: int = 50,
):
    sensor = await db.get(Sensor, sensor_id)
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    rows = await get_sensor_history(db, sensor, limit=min(limit, 200))
    return [SensorHistoryPoint(**row) for row in rows]
