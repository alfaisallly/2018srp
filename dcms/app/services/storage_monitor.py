import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    DeviceStatus,
    ProtocolType,
    StorageMetric,
    StorageSystem,
    StorageVendor,
)
from app.services.snmp_collector import snmp_get_bulk
from app.services.ssh_connector import run_ssh_command


VENDOR_SNMP_OIDS: dict[StorageVendor, dict[str, str]] = {
    StorageVendor.NETAPP: {
        "total_kb": "1.3.6.1.4.1.789.1.5.4.1.1.0",
        "used_kb": "1.3.6.1.4.1.789.1.5.4.1.2.0",
    },
    StorageVendor.DELL_EMC: {
        "total_kb": "1.3.6.1.4.1.674.10893.1.8.1.1.1.4.1.0",
    },
    StorageVendor.HPE: {
        "total_kb": "1.3.6.1.4.1.232.9.2.2.4.1.1.0",
    },
    StorageVendor.GENERIC: {
        "total_kb": "1.3.6.1.2.1.25.2.3.0",
    },
}


async def poll_storage(db: AsyncSession, storage_id: int) -> dict:
    result = await db.execute(
        select(StorageSystem).options(selectinload(StorageSystem.credentials)).where(StorageSystem.id == storage_id)
    )
    storage = result.scalar_one_or_none()
    if not storage:
        return {"success": False, "error": "Storage not found"}

    protocol_used = None
    error = None
    metrics: list[tuple[str, float, str | None]] = []

    for cred in storage.credentials:
        try:
            if cred.protocol == ProtocolType.SNMP and cred.community:
                metrics = await _poll_snmp(storage, cred.community, cred.port or 161)
                protocol_used = "snmp"
                break
            if cred.protocol == ProtocolType.REST and cred.api_token:
                metrics = await _poll_rest(storage, cred.api_token, cred.port or 443)
                protocol_used = "rest"
                break
            if cred.protocol == ProtocolType.SSH and cred.username and cred.password:
                metrics = await _poll_ssh(storage, cred.username, cred.password, cred.port or 22)
                protocol_used = "ssh"
                break
        except Exception as exc:
            error = str(exc)
            continue

    if metrics or protocol_used:
        storage.status = DeviceStatus.ONLINE
        storage.last_seen = datetime.now(timezone.utc)
        for name, value, unit in metrics:
            db.add(StorageMetric(storage_id=storage.id, metric_name=name, metric_value=value, unit=unit))
            if name == "total_capacity_tb":
                storage.total_capacity_tb = value
            if name == "used_capacity_tb":
                storage.used_capacity_tb = value
        await _check_storage_thresholds(db, storage, metrics)
        await db.flush()
        usage = None
        if storage.total_capacity_tb and storage.used_capacity_tb and storage.total_capacity_tb > 0:
            usage = round((storage.used_capacity_tb / storage.total_capacity_tb) * 100, 1)
        return {
            "success": True,
            "protocol": protocol_used,
            "hostname": storage.hostname,
            "capacity_usage_pct": usage,
        }

    storage.status = DeviceStatus.OFFLINE
    await db.flush()
    await _create_storage_alert(
        db, storage, f"Storage unreachable: {storage.name}", error or "All protocols failed", AlertSeverity.CRITICAL
    )
    return {"success": False, "error": error or "All protocols failed"}


async def _poll_snmp(storage: StorageSystem, community: str, port: int) -> list[tuple[str, float, str | None]]:
    oids = dict(VENDOR_SNMP_OIDS.get(storage.vendor, VENDOR_SNMP_OIDS[StorageVendor.GENERIC]))
    oids["sysName"] = "1.3.6.1.2.1.1.5.0"
    data = await asyncio.to_thread(snmp_get_bulk, storage.ip_address, community, oids, port)
    metrics: list[tuple[str, float, str | None]] = [("reachable", 1.0, "bool")]

    if "total_kb" in data:
        try:
            total_tb = float(data["total_kb"]) / (1024 * 1024)
            metrics.append(("total_capacity_tb", total_tb, "TB"))
        except ValueError:
            pass
    if "used_kb" in data:
        try:
            used_tb = float(data["used_kb"]) / (1024 * 1024)
            metrics.append(("used_capacity_tb", used_tb, "TB"))
        except ValueError:
            pass

    total_tb = next((v for n, v, _ in metrics if n == "total_capacity_tb"), None)
    used_tb = next((v for n, v, _ in metrics if n == "used_capacity_tb"), None)
    if total_tb and used_tb and total_tb > 0:
        metrics.append(("capacity_usage", (used_tb / total_tb) * 100, "%"))

    return metrics


async def _poll_rest(storage: StorageSystem, token: str, port: int) -> list[tuple[str, float, str | None]]:
    from app.services.rest_api_connector import rest_get

    if storage.vendor == StorageVendor.QNAP:
        data = await rest_get(storage.ip_address, "/api/v1/storage/info", token, port, verify_ssl=False)
    elif storage.vendor == StorageVendor.SYNOLOGY:
        data = await rest_get(storage.ip_address, "/webapi/entry.cgi?api=SYNO.Storage.CGI.Storage&method=load_info", token, port, verify_ssl=False)
    else:
        data = await rest_get(storage.ip_address, "/api/storage/capacity", token, port, verify_ssl=False)

    metrics: list[tuple[str, float, str | None]] = [("reachable", 1.0, "bool")]
    if isinstance(data, dict):
        total = data.get("total_tb") or data.get("total_size", 0)
        used = data.get("used_tb") or data.get("used_size", 0)
        if total:
            metrics.append(("total_capacity_tb", float(total), "TB"))
        if used:
            metrics.append(("used_capacity_tb", float(used), "TB"))
    return metrics


async def _poll_ssh(storage: StorageSystem, username: str, password: str, port: int) -> list[tuple[str, float, str | None]]:
    output = await asyncio.to_thread(run_ssh_command, storage.ip_address, username, password, "df -h --total | tail -1", port)
    parts = output.split()
    metrics: list[tuple[str, float, str | None]] = [("reachable", 1.0, "bool")]
    if len(parts) >= 5:
        usage_str = parts[4].replace("%", "")
        try:
            metrics.append(("capacity_usage", float(usage_str), "%"))
        except ValueError:
            pass
    return metrics


async def _check_storage_thresholds(
    db: AsyncSession, storage: StorageSystem, metrics: list[tuple[str, float, str | None]]
) -> None:
    for name, value, _ in metrics:
        if name == "capacity_usage" and value > 85:
            await _create_storage_alert(
                db, storage, f"Storage almost full: {storage.name}", f"Usage {value}%", AlertSeverity.WARNING
            )
        if name == "capacity_usage" and value > 95:
            await _create_storage_alert(
                db, storage, f"Storage critical: {storage.name}", f"Usage {value}%", AlertSeverity.CRITICAL
            )


async def _create_storage_alert(
    db: AsyncSession, storage: StorageSystem, title: str, message: str, severity: AlertSeverity
) -> None:
    existing = await db.execute(
        select(Alert).where(
            Alert.storage_id == storage.id,
            Alert.title == title,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
        )
    )
    if existing.scalar_one_or_none():
        return
    db.add(
        Alert(
            storage_id=storage.id,
            datacenter_id=storage.datacenter_id,
            title=title,
            message=message,
            severity=severity,
            source="storage_monitor",
        )
    )


async def poll_all_storage(db: AsyncSession) -> dict:
    result = await db.execute(select(StorageSystem.id))
    ids = [row[0] for row in result.all()]
    stats = {"total": len(ids), "online": 0, "offline": 0}
    for sid in ids:
        r = await poll_storage(db, sid)
        if r.get("success"):
            stats["online"] += 1
        else:
            stats["offline"] += 1
    return stats
