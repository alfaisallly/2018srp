"""PRTG-like sensor evaluation, seeding, and alert lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Device,
    DeviceMetric,
    Sensor,
    SensorAssetType,
    SensorStatus,
    Server,
    ServerMetric,
    StorageMetric,
    StorageSystem,
)

SENSOR_STATUS_COLORS = {
    SensorStatus.UP: "#22c55e",
    SensorStatus.WARNING: "#eab308",
    SensorStatus.DOWN: "#ef4444",
    SensorStatus.PAUSED: "#3b82f6",
    SensorStatus.UNKNOWN: "#64748b",
}

SENSOR_STATUS_LABELS = {
    SensorStatus.UP: "طبيعي",
    SensorStatus.WARNING: "تحذير",
    SensorStatus.DOWN: "تعطل",
    SensorStatus.PAUSED: "موقوف",
    SensorStatus.UNKNOWN: "غير معروف",
}


@dataclass(frozen=True)
class SensorTemplate:
    name: str
    unit: str | None
    warning: float | None
    error: float | None
    higher_is_worse: bool = True


DEFAULT_SENSOR_TEMPLATES: dict[str, SensorTemplate] = {
    "reachable": SensorTemplate("الاتصال", "bool", None, 0.5, higher_is_worse=False),
    "cpu_utilization": SensorTemplate("المعالج CPU", "%", 80, 90),
    "memory_usage": SensorTemplate("الذاكرة", "%", 80, 90),
    "memory_used": SensorTemplate("الذاكرة المستخدمة", "bytes", None, None),
    "disk_usage_root": SensorTemplate("قرص الجذر /", "%", 85, 95),
    "capacity_usage": SensorTemplate("استخدام التخزين", "%", 85, 95),
    "load_1m": SensorTemplate("حمل النظام 1د", "load", 5, 10),
    "buffer_utilization": SensorTemplate("استخدام Buffer", "%", 80, 90),
    "active_sessions": SensorTemplate("الجلسات النشطة", "count", 50000, 100000),
    "ipmi_sensors": SensorTemplate("حساسات IPMI", "count", None, None),
}


def evaluate_sensor_value(
    value: float | None,
    *,
    warning_limit: float | None,
    error_limit: float | None,
    higher_is_worse: bool = True,
    enabled: bool = True,
) -> tuple[SensorStatus, str]:
    if not enabled:
        return SensorStatus.PAUSED, "الحساس موقوف"
    if value is None:
        return SensorStatus.UNKNOWN, "لا توجد قيمة"

    if higher_is_worse:
        if error_limit is not None and value >= error_limit:
            return SensorStatus.DOWN, f"تجاوز حد الخطأ ({error_limit})"
        if warning_limit is not None and value >= warning_limit:
            return SensorStatus.WARNING, f"تجاوز حد التحذير ({warning_limit})"
    else:
        if error_limit is not None and value < error_limit:
            return SensorStatus.DOWN, f"أقل من حد الخطأ ({error_limit})"
        if warning_limit is not None and value < warning_limit:
            return SensorStatus.WARNING, f"أقل من حد التحذير ({warning_limit})"

    return SensorStatus.UP, "طبيعي"


def _severity_for_status(status: SensorStatus) -> AlertSeverity:
    if status == SensorStatus.DOWN:
        return AlertSeverity.CRITICAL
    if status == SensorStatus.WARNING:
        return AlertSeverity.WARNING
    return AlertSeverity.INFO


async def ensure_sensors_for_asset(
    db: AsyncSession,
    *,
    asset_type: SensorAssetType,
    asset_id: int,
    datacenter_id: int,
    metric_keys: set[str],
) -> list[Sensor]:
    query = select(Sensor).where(Sensor.asset_type == asset_type)
    if asset_type == SensorAssetType.DEVICE:
        query = query.where(Sensor.device_id == asset_id)
    elif asset_type == SensorAssetType.SERVER:
        query = query.where(Sensor.server_id == asset_id)
    else:
        query = query.where(Sensor.storage_id == asset_id)

    result = await db.execute(query)
    existing = {s.metric_key: s for s in result.scalars().all()}
    sensors: list[Sensor] = list(existing.values())

    keys_to_create = {"reachable"} | metric_keys
    for key in keys_to_create:
        if key in existing:
            continue
        template = DEFAULT_SENSOR_TEMPLATES.get(key)
        if not template and key not in metric_keys:
            continue
        sensor = Sensor(
            datacenter_id=datacenter_id,
            device_id=asset_id if asset_type == SensorAssetType.DEVICE else None,
            server_id=asset_id if asset_type == SensorAssetType.SERVER else None,
            storage_id=asset_id if asset_type == SensorAssetType.STORAGE else None,
            asset_type=asset_type,
            name=template.name if template else key,
            metric_key=key,
            unit=template.unit if template else None,
            warning_limit=template.warning if template else None,
            error_limit=template.error if template else None,
            higher_is_worse=template.higher_is_worse if template else True,
        )
        db.add(sensor)
        sensors.append(sensor)

    await db.flush()
    return sensors


async def _resolve_sensor_alerts(db: AsyncSession, sensor_id: int) -> None:
    result = await db.execute(
        select(Alert).where(
            Alert.sensor_id == sensor_id,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
        )
    )
    now = datetime.now(timezone.utc)
    for alert in result.scalars().all():
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = now


async def _create_sensor_alert(
    db: AsyncSession,
    sensor: Sensor,
    *,
    asset_name: str,
    status: SensorStatus,
    message: str,
    value: float | None,
) -> None:
    existing = await db.execute(
        select(Alert).where(
            Alert.sensor_id == sensor.id,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
        )
    )
    if existing.scalar_one_or_none():
        return

    alert = Alert(
        sensor_id=sensor.id,
        device_id=sensor.device_id,
        server_id=sensor.server_id,
        storage_id=sensor.storage_id,
        datacenter_id=sensor.datacenter_id,
        title=f"حساس {sensor.name}: {asset_name}",
        message=message,
        severity=_severity_for_status(status),
        source="sensor_monitor",
        metadata_={"metric_key": sensor.metric_key, "value": value, "status": status.value},
    )
    db.add(alert)


async def process_sensor_metrics(
    db: AsyncSession,
    *,
    asset_type: SensorAssetType,
    asset_id: int,
    datacenter_id: int,
    asset_name: str,
    metrics: dict[str, tuple[float, str | None]],
) -> dict[str, int]:
    sensors = await ensure_sensors_for_asset(
        db,
        asset_type=asset_type,
        asset_id=asset_id,
        datacenter_id=datacenter_id,
        metric_keys=set(metrics.keys()),
    )

    counts = {"up": 0, "warning": 0, "down": 0, "paused": 0, "unknown": 0}
    now = datetime.now(timezone.utc)

    for sensor in sensors:
        if not sensor.enabled:
            sensor.last_status = SensorStatus.PAUSED
            sensor.last_check_at = now
            counts["paused"] += 1
            continue

        metric = metrics.get(sensor.metric_key)
        value = metric[0] if metric else None
        if metric and metric[1]:
            sensor.unit = metric[1]

        status, msg = evaluate_sensor_value(
            value,
            warning_limit=sensor.warning_limit,
            error_limit=sensor.error_limit,
            higher_is_worse=sensor.higher_is_worse,
            enabled=sensor.enabled,
        )

        sensor.last_value = value
        sensor.last_status = status
        sensor.last_message = msg
        sensor.last_check_at = now
        counts[status.value] += 1

        if status == SensorStatus.UP:
            await _resolve_sensor_alerts(db, sensor.id)
        elif status in (SensorStatus.WARNING, SensorStatus.DOWN):
            display = f"{value}{sensor.unit or ''}" if value is not None else "—"
            await _create_sensor_alert(
                db,
                sensor,
                asset_name=asset_name,
                status=status,
                message=f"{msg} — القيمة الحالية: {display}",
                value=value,
            )

    await db.flush()
    return counts


async def mark_asset_sensors_down(
    db: AsyncSession,
    *,
    asset_type: SensorAssetType,
    asset_id: int,
    datacenter_id: int,
    asset_name: str,
    message: str,
) -> None:
    sensors = await ensure_sensors_for_asset(
        db,
        asset_type=asset_type,
        asset_id=asset_id,
        datacenter_id=datacenter_id,
        metric_keys=set(),
    )
    now = datetime.now(timezone.utc)
    for sensor in sensors:
        if sensor.metric_key == "reachable":
            sensor.last_value = 0.0
            sensor.last_status = SensorStatus.DOWN
            sensor.last_message = message
            sensor.last_check_at = now
            await _create_sensor_alert(
                db,
                sensor,
                asset_name=asset_name,
                status=SensorStatus.DOWN,
                message=message,
                value=0.0,
            )
        else:
            sensor.last_status = SensorStatus.UNKNOWN
            sensor.last_message = "الأصل غير متصل"
            sensor.last_check_at = now


async def get_sensor_history(
    db: AsyncSession,
    sensor: Sensor,
    *,
    limit: int = 50,
) -> list[dict]:
    model = DeviceMetric
    fk_col = DeviceMetric.device_id
    asset_id = sensor.device_id

    if sensor.asset_type == SensorAssetType.SERVER:
        model = ServerMetric
        fk_col = ServerMetric.server_id
        asset_id = sensor.server_id
    elif sensor.asset_type == SensorAssetType.STORAGE:
        model = StorageMetric
        fk_col = StorageMetric.storage_id
        asset_id = sensor.storage_id

    if not asset_id:
        return []

    result = await db.execute(
        select(model)
        .where(fk_col == asset_id, model.metric_name == sensor.metric_key)
        .order_by(model.collected_at.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())
    return [
        {
            "value": row.metric_value,
            "unit": row.unit,
            "collected_at": row.collected_at,
        }
        for row in reversed(rows)
    ]


async def get_sensor_summary(db: AsyncSession, datacenter_id: int | None = None) -> dict:
    query = select(Sensor.last_status, func.count(Sensor.id)).group_by(Sensor.last_status)
    if datacenter_id:
        query = query.where(Sensor.datacenter_id == datacenter_id)
    result = await db.execute(query)
    summary = {status.value: 0 for status in SensorStatus}
    total = 0
    for status, count in result.all():
        summary[status.value] = count
        total += count
    summary["total"] = total
    return summary


async def seed_all_sensors(db: AsyncSession) -> dict:
    created = 0
    specs = (
        (Device, SensorAssetType.DEVICE, Sensor.device_id),
        (Server, SensorAssetType.SERVER, Sensor.server_id),
        (StorageSystem, SensorAssetType.STORAGE, Sensor.storage_id),
    )
    for model, asset_type, fk in specs:
        result = await db.execute(select(model))
        for asset in result.scalars().all():
            before = await db.scalar(select(func.count(Sensor.id)).where(fk == asset.id)) or 0
            await ensure_sensors_for_asset(
                db,
                asset_type=asset_type,
                asset_id=asset.id,
                datacenter_id=asset.datacenter_id,
                metric_keys=set(),
            )
            after = await db.scalar(select(func.count(Sensor.id)).where(fk == asset.id)) or 0
            created += max(0, after - before)
    return {"created": created}
