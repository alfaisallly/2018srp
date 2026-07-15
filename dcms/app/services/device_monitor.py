from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Device,
    DeviceCredential,
    DeviceMetric,
    DeviceStatus,
    ProtocolType,
    VendorType,
)
from app.vendors import get_vendor_adapter


async def poll_device(db: AsyncSession, device_id: int) -> dict:
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.credentials))
        .where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        return {"success": False, "error": "Device not found"}

    adapter = get_vendor_adapter(device.vendor)
    info = None
    metrics = []
    protocol_used = None
    error = None

    for cred in device.credentials:
        try:
            if cred.protocol == ProtocolType.SNMP and cred.community:
                info = await adapter.collect_snmp(device.ip_address, cred.community, cred.port or 161)
                metrics = await adapter.get_metrics_snmp(device.ip_address, cred.community, cred.port or 161)
                protocol_used = "snmp"
                break
            if cred.protocol == ProtocolType.SSH and cred.username and cred.password:
                info = await adapter.collect_ssh(
                    device.ip_address, cred.username, cred.password, cred.port or 22
                )
                protocol_used = "ssh"
                break
            if cred.protocol == ProtocolType.NETCONF and cred.username and cred.password:
                info = await adapter.collect_netconf(
                    device.ip_address, cred.username, cred.password, cred.port or 830
                )
                protocol_used = "netconf"
                break
            if cred.protocol == ProtocolType.REST and cred.api_token:
                info = await adapter.collect_rest(device.ip_address, cred.api_token, cred.port or 443)
                protocol_used = "rest"
                break
        except Exception as exc:
            error = str(exc)
            continue

    if info:
        device.status = DeviceStatus.ONLINE
        device.last_seen = datetime.now(timezone.utc)
        if info.hostname:
            device.hostname = info.hostname
        if info.model:
            device.model = info.model
        if info.serial_number:
            device.serial_number = info.serial_number

        for metric in metrics:
            db.add(
                DeviceMetric(
                    device_id=device.id,
                    metric_name=metric.name,
                    metric_value=metric.value,
                    unit=metric.unit,
                )
            )

        await _check_thresholds(db, device, metrics)
        await db.flush()
        return {"success": True, "protocol": protocol_used, "hostname": info.hostname}

    device.status = DeviceStatus.OFFLINE
    await db.flush()
    await _create_alert(
        db,
        device,
        title=f"Device unreachable: {device.name}",
        message=error or "All configured protocols failed",
        severity=AlertSeverity.CRITICAL,
    )
    return {"success": False, "error": error or "All protocols failed"}


async def _check_thresholds(db: AsyncSession, device: Device, metrics: list) -> None:
    for metric in metrics:
        if metric.name == "cpu_utilization" and metric.value > 90:
            await _create_alert(
                db,
                device,
                title=f"High CPU on {device.name}",
                message=f"CPU utilization is {metric.value}%",
                severity=AlertSeverity.WARNING,
            )
        if metric.name == "memory_usage" and metric.value > 90:
            await _create_alert(
                db,
                device,
                title=f"High memory on {device.name}",
                message=f"Memory usage is {metric.value}%",
                severity=AlertSeverity.WARNING,
            )


async def _create_alert(
    db: AsyncSession,
    device: Device,
    title: str,
    message: str,
    severity: AlertSeverity,
) -> None:
    existing = await db.execute(
        select(Alert).where(
            Alert.device_id == device.id,
            Alert.title == title,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
        )
    )
    if existing.scalar_one_or_none():
        return

    db.add(
        Alert(
            device_id=device.id,
            datacenter_id=device.datacenter_id,
            title=title,
            message=message,
            severity=severity,
            source="monitor",
        )
    )


async def poll_all_devices(db: AsyncSession) -> dict:
    result = await db.execute(select(Device.id))
    device_ids = [row[0] for row in result.all()]
    results = {"total": len(device_ids), "online": 0, "offline": 0, "errors": []}
    for device_id in device_ids:
        poll_result = await poll_device(db, device_id)
        if poll_result.get("success"):
            results["online"] += 1
        else:
            results["offline"] += 1
            results["errors"].append({"device_id": device_id, "error": poll_result.get("error")})
    return results
