"""Aggregated datacenter overview for dashboard detail view."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    DataCenter,
    Device,
    DeviceStatus,
    DeviceType,
    NetworkMap,
    Sensor,
    SensorStatus,
    Server,
    StorageSystem,
    VendorType,
)
from app.services.sensor_engine import SENSOR_STATUS_COLORS, SENSOR_STATUS_LABELS


def infer_device_type(vendor: VendorType, name: str = "", model: str | None = None) -> DeviceType:
    text = f"{name} {model or ''}".lower()
    if vendor == VendorType.FORTINET or "firewall" in text or "fw-" in text or "-fw" in text:
        return DeviceType.FIREWALL
    if "router" in text or "rt-" in text or "-rt" in text:
        return DeviceType.ROUTER
    if vendor in (VendorType.CISCO, VendorType.JUNIPER):
        return DeviceType.SWITCH
    return DeviceType.OTHER


def _device_brief(d: Device) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "hostname": d.hostname,
        "ip_address": d.ip_address,
        "vendor": d.vendor.value,
        "device_type": d.device_type.value,
        "model": d.model,
        "status": d.status.value,
        "last_seen": d.last_seen,
    }


async def get_datacenter_overview(db: AsyncSession, datacenter_id: int) -> dict:
    dc_result = await db.execute(select(DataCenter).where(DataCenter.id == datacenter_id))
    datacenter = dc_result.scalar_one_or_none()
    if not datacenter:
        raise ValueError("Data center not found")

    devices_result = await db.execute(
        select(Device).where(Device.datacenter_id == datacenter_id).order_by(Device.name)
    )
    devices = list(devices_result.scalars().all())

    servers_result = await db.execute(
        select(Server).where(Server.datacenter_id == datacenter_id).order_by(Server.name)
    )
    servers = list(servers_result.scalars().all())

    storage_result = await db.execute(
        select(StorageSystem).where(StorageSystem.datacenter_id == datacenter_id).order_by(StorageSystem.name)
    )
    storage_items = list(storage_result.scalars().all())

    maps_result = await db.execute(
        select(NetworkMap).where(NetworkMap.datacenter_id == datacenter_id).order_by(NetworkMap.name)
    )
    maps = list(maps_result.scalars().all())

    alerts_result = await db.execute(
        select(Alert)
        .where(Alert.datacenter_id == datacenter_id, Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]))
        .order_by(Alert.created_at.desc())
        .limit(20)
    )
    alerts = list(alerts_result.scalars().all())

    sensors_result = await db.execute(select(Sensor).where(Sensor.datacenter_id == datacenter_id))
    sensors = list(sensors_result.scalars().all())

    switches = [d for d in devices if d.device_type == DeviceType.SWITCH]
    firewalls = [d for d in devices if d.device_type == DeviceType.FIREWALL]
    routers = [d for d in devices if d.device_type == DeviceType.ROUTER]
    other_devices = [d for d in devices if d.device_type == DeviceType.OTHER]

    sensor_counts = {s.value: 0 for s in SensorStatus}
    for s in sensors:
        sensor_counts[s.last_status.value] += 1

    return {
        "datacenter": {
            "id": datacenter.id,
            "name": datacenter.name,
            "location": datacenter.location,
            "description": datacenter.description,
            "contact_email": datacenter.contact_email,
            "created_at": datacenter.created_at,
        },
        "summary": {
            "switches": len(switches),
            "firewalls": len(firewalls),
            "routers": len(routers),
            "other_devices": len(other_devices),
            "total_devices": len(devices),
            "online_devices": sum(1 for d in devices if d.status == DeviceStatus.ONLINE),
            "servers": len(servers),
            "online_servers": sum(1 for s in servers if s.status == DeviceStatus.ONLINE),
            "storage": len(storage_items),
            "online_storage": sum(1 for st in storage_items if st.status == DeviceStatus.ONLINE),
            "open_alerts": len(alerts),
            "critical_alerts": sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL),
            "network_maps": len(maps),
            "total_sensors": len(sensors),
            "sensors_up": sensor_counts.get("up", 0),
            "sensors_warning": sensor_counts.get("warning", 0),
            "sensors_down": sensor_counts.get("down", 0),
        },
        "switches": [_device_brief(d) for d in switches],
        "firewalls": [_device_brief(d) for d in firewalls],
        "routers": [_device_brief(d) for d in routers],
        "other_devices": [_device_brief(d) for d in other_devices],
        "servers": [
            {
                "id": s.id,
                "name": s.name,
                "hostname": s.hostname,
                "ip_address": s.ip_address,
                "os_type": s.os_type.value,
                "server_role": s.server_role.value,
                "status": s.status.value,
                "last_seen": s.last_seen,
            }
            for s in servers
        ],
        "storage": [
            {
                "id": st.id,
                "name": st.name,
                "hostname": st.hostname,
                "ip_address": st.ip_address,
                "vendor": st.vendor.value,
                "storage_type": st.storage_type.value,
                "model": st.model,
                "total_capacity_tb": st.total_capacity_tb,
                "used_capacity_tb": st.used_capacity_tb,
                "status": st.status.value,
                "last_seen": st.last_seen,
            }
            for st in storage_items
        ],
        "network_maps": [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "topology": m.topology,
                "updated_at": m.updated_at,
            }
            for m in maps
        ],
        "alerts": [
            {
                "id": a.id,
                "title": a.title,
                "message": a.message,
                "severity": a.severity.value,
                "status": a.status.value,
                "source": a.source,
                "created_at": a.created_at,
            }
            for a in alerts
        ],
        "sensors": [
            {
                "id": s.id,
                "name": s.name,
                "asset_type": s.asset_type.value,
                "metric_key": s.metric_key,
                "last_value": s.last_value,
                "unit": s.unit,
                "last_status": s.last_status.value,
                "status_color": SENSOR_STATUS_COLORS.get(s.last_status, "#64748b"),
                "status_label": SENSOR_STATUS_LABELS.get(s.last_status, s.last_status.value),
                "last_check_at": s.last_check_at,
            }
            for s in sensors
        ],
    }


async def get_combined_overview(db: AsyncSession) -> dict:
    result = await db.execute(select(DataCenter).order_by(DataCenter.name))
    datacenters = list(result.scalars().all())
    overviews = []
    combined = {
        "switches": 0,
        "firewalls": 0,
        "routers": 0,
        "other_devices": 0,
        "total_devices": 0,
        "online_devices": 0,
        "servers": 0,
        "online_servers": 0,
        "storage": 0,
        "online_storage": 0,
        "open_alerts": 0,
        "critical_alerts": 0,
        "network_maps": 0,
        "total_sensors": 0,
        "sensors_up": 0,
        "sensors_warning": 0,
        "sensors_down": 0,
    }
    for dc in datacenters:
        overview = await get_datacenter_overview(db, dc.id)
        overviews.append(overview)
        s = overview["summary"]
        for key in combined:
            combined[key] += s.get(key, 0)
    return {
        "datacenters": [
            {
                "id": d.id,
                "name": d.name,
                "location": d.location,
                "description": d.description,
                "contact_email": d.contact_email,
                "created_at": d.created_at,
            }
            for d in datacenters
        ],
        "combined_summary": combined,
        "overviews": overviews,
    }
