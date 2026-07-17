"""Configuration backup for Cisco/Juniper network devices via SSH."""

import asyncio
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Device, DeviceConfigBackup, ProtocolType, VendorType


def _config_command(vendor: VendorType) -> str:
    if vendor == VendorType.JUNIPER:
        return "show configuration | display set"
    return "show running-config"


async def backup_device_config(session: AsyncSession, device_id: int) -> DeviceConfigBackup:
    result = await session.execute(
        select(Device).options(selectinload(Device.credentials)).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise ValueError("Device not found")
    if device.vendor not in (VendorType.CISCO, VendorType.JUNIPER):
        raise ValueError("Config backup supported for Cisco and Juniper only")

    cred = next((c for c in device.credentials if c.protocol == ProtocolType.SSH), None)
    if not cred or not cred.username or not cred.password:
        raise ValueError("SSH credentials required for config backup")

    from app.services.ssh_connector import run_ssh_command

    cmd = _config_command(device.vendor)
    port = cred.port or 22
    content = await asyncio.to_thread(
        run_ssh_command, device.ip_address, cred.username, cred.password, cmd, port
    )
    if not content or len(content.strip()) < 10:
        raise ValueError("Empty or invalid config received")

    content_hash = hashlib.sha256(content.encode()).hexdigest()
    latest = await session.execute(
        select(DeviceConfigBackup)
        .where(DeviceConfigBackup.device_id == device_id)
        .order_by(DeviceConfigBackup.collected_at.desc())
        .limit(1)
    )
    prev = latest.scalar_one_or_none()
    if prev and prev.content_hash == content_hash:
        return prev

    backup = DeviceConfigBackup(
        device_id=device_id,
        protocol=ProtocolType.SSH,
        content=content,
        content_hash=content_hash,
        size_bytes=len(content.encode()),
    )
    session.add(backup)
    await session.flush()
    await session.refresh(backup)
    return backup


async def backup_all_eligible(session: AsyncSession, datacenter_id: int | None = None) -> dict:
    q = select(Device).where(Device.vendor.in_([VendorType.CISCO, VendorType.JUNIPER]))
    if datacenter_id:
        q = q.where(Device.datacenter_id == datacenter_id)
    devices = list((await session.execute(q)).scalars().all())
    ok, skipped, failed = 0, 0, 0
    errors: list[str] = []
    for device in devices:
        try:
            prev_q = await session.execute(
                select(DeviceConfigBackup)
                .where(DeviceConfigBackup.device_id == device.id)
                .order_by(DeviceConfigBackup.collected_at.desc())
                .limit(1)
            )
            before_id = prev_q.scalar_one_or_none()
            before_hash = before_id.content_hash if before_id else None
            backup = await backup_device_config(session, device.id)
            if before_hash and backup.content_hash == before_hash:
                skipped += 1
            else:
                ok += 1
        except Exception as exc:
            failed += 1
            errors.append(f"{device.name}: {exc}")
    return {"success": ok, "unchanged": skipped, "failed": failed, "errors": errors[:20]}
