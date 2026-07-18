from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_permission
from app.database import get_db
from app.models import Permission, StorageCredential, StorageSystem, User
from app.schemas import MonitoringGuide, StorageCreate, StoragePollResult, StorageResponse
from app.services.monitoring_guide import MONITORING_GUIDES
from app.services.storage_monitor import poll_all_storage, poll_storage

router = APIRouter(prefix="/storage", tags=["Storage"])


@router.get("/monitoring-guide", response_model=MonitoringGuide)
async def storage_monitoring_guide(_: Annotated[User, Depends(require_permission(Permission.VIEW))]):
    return MonitoringGuide(**MONITORING_GUIDES["storage"])


@router.get("", response_model=list[StorageResponse])
async def list_storage(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = select(StorageSystem).order_by(StorageSystem.name)
    if datacenter_id:
        query = query.where(StorageSystem.datacenter_id == datacenter_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=StorageResponse, status_code=status.HTTP_201_CREATED)
async def create_storage(
    payload: StorageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_STORAGE))],
):
    storage = StorageSystem(
        datacenter_id=payload.datacenter_id,
        rack_id=payload.rack_id,
        name=payload.name,
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        vendor=payload.vendor,
        model=payload.model,
        storage_type=payload.storage_type,
        total_capacity_tb=payload.total_capacity_tb,
        position_u=payload.position_u,
        notes=payload.notes,
    )
    db.add(storage)
    await db.flush()
    for cred in payload.credentials:
        db.add(StorageCredential(storage_id=storage.id, **cred.model_dump()))
    await db.refresh(storage)
    return storage


@router.post("/poll-all")
async def poll_all_storage_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_STORAGE))],
):
    return await poll_all_storage(db)


@router.get("/{storage_id}", response_model=StorageResponse)
async def get_storage(
    storage_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(StorageSystem).where(StorageSystem.id == storage_id))
    storage = result.scalar_one_or_none()
    if not storage:
        raise HTTPException(status_code=404, detail="Storage not found")
    return storage


@router.get("/{storage_id}/credentials")
async def get_storage_credentials(
    storage_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_STORAGE))],
):
    result = await db.execute(
        select(StorageSystem).options(selectinload(StorageSystem.credentials)).where(StorageSystem.id == storage_id)
    )
    storage = result.scalar_one_or_none()
    if not storage:
        raise HTTPException(status_code=404, detail="Storage not found")
    return [
        {
            "id": c.id,
            "protocol": c.protocol.value,
            "username": c.username,
            "port": c.port,
            "has_password": bool(c.password),
            "has_community": bool(c.community),
            "has_token": bool(c.api_token),
        }
        for c in storage.credentials
    ]


@router.post("/{storage_id}/poll", response_model=StoragePollResult)
async def poll_storage_endpoint(
    storage_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_STORAGE))],
):
    result = await poll_storage(db, storage_id)
    return StoragePollResult(**result)


@router.delete("/{storage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_storage(
    storage_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_STORAGE))],
):
    result = await db.execute(select(StorageSystem).where(StorageSystem.id == storage_id))
    storage = result.scalar_one_or_none()
    if not storage:
        raise HTTPException(status_code=404, detail="Storage not found")
    await db.delete(storage)
