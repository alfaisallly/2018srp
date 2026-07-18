from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_permission
from app.database import get_db
from app.models import Device, DeviceConfigBackup, Permission, User, VendorType
from app.schemas import ConfigBackupDetail, ConfigBackupResponse, ConfigBackupRunResult
from app.services.config_backup import backup_all_eligible, backup_device_config

router = APIRouter(prefix="/backups", tags=["Config Backups"])


@router.get("", response_model=list[ConfigBackupResponse])
async def list_backups(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    device_id: int | None = None,
    datacenter_id: int | None = None,
    limit: int = 100,
):
    query = (
        select(DeviceConfigBackup)
        .join(Device)
        .order_by(DeviceConfigBackup.collected_at.desc())
        .limit(min(limit, 500))
    )
    if device_id:
        query = query.where(DeviceConfigBackup.device_id == device_id)
    if datacenter_id:
        query = query.where(Device.datacenter_id == datacenter_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/devices/eligible")
async def list_eligible_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = (
        select(Device)
        .options(selectinload(Device.credentials))
        .where(Device.vendor.in_([VendorType.CISCO, VendorType.JUNIPER, VendorType.PALO_ALTO]))
        .order_by(Device.name)
    )
    if datacenter_id:
        query = query.where(Device.datacenter_id == datacenter_id)
    result = await db.execute(query)
    devices = list(result.scalars().all())
    return [
        {
            "id": d.id,
            "name": d.name,
            "vendor": d.vendor.value,
            "ip_address": d.ip_address,
            "has_ssh": any(c.protocol.value == "ssh" and c.username and c.password for c in d.credentials),
        }
        for d in devices
    ]


@router.get("/{backup_id}", response_model=ConfigBackupDetail)
async def get_backup(
    backup_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(DeviceConfigBackup).where(DeviceConfigBackup.id == backup_id))
    backup = result.scalar_one_or_none()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    return backup


@router.post("/devices/{device_id}", response_model=ConfigBackupResponse)
async def backup_device(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    try:
        return await backup_device_config(db, device_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run-all", response_model=ConfigBackupRunResult)
async def run_all_backups(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
    datacenter_id: int | None = None,
):
    return await backup_all_eligible(db, datacenter_id)
