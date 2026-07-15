from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_permission
from app.database import get_db
from app.models import Device, DeviceCredential, Permission, User
from app.schemas import DeviceCreate, DeviceResponse, PollResult
from app.services.device_monitor import poll_device

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = select(Device).order_by(Device.name)
    if datacenter_id:
        query = query.where(Device.datacenter_id == datacenter_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    payload: DeviceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    device = Device(
        datacenter_id=payload.datacenter_id,
        rack_id=payload.rack_id,
        name=payload.name,
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        vendor=payload.vendor,
        model=payload.model,
        position_u=payload.position_u,
        height_u=payload.height_u,
        tags=payload.tags,
    )
    db.add(device)
    await db.flush()

    for cred in payload.credentials:
        db.add(DeviceCredential(device_id=device.id, **cred.model_dump()))

    await db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/{device_id}/poll", response_model=PollResult)
async def poll_device_endpoint(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    result = await poll_device(db, device_id)
    return PollResult(**result)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    await db.delete(device)
