from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.database import get_db
from app.models import DataCenter, Permission, Rack, User
from app.schemas import (
    DataCenterCreate,
    DataCenterOverview,
    DataCenterResponse,
    RackCreate,
    RackResponse,
)
from app.services.datacenter_overview import get_datacenter_overview

router = APIRouter(prefix="/datacenters", tags=["Data Centers"])


@router.get("", response_model=list[DataCenterResponse])
async def list_datacenters(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(DataCenter).order_by(DataCenter.name))
    return list(result.scalars().all())


@router.post("", response_model=DataCenterResponse, status_code=status.HTTP_201_CREATED)
async def create_datacenter(
    payload: DataCenterCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DATACENTERS))],
):
    dc = DataCenter(**payload.model_dump())
    db.add(dc)
    await db.flush()
    await db.refresh(dc)
    return dc


@router.get("/{datacenter_id}", response_model=DataCenterResponse)
async def get_datacenter(
    datacenter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(DataCenter).where(DataCenter.id == datacenter_id))
    dc = result.scalar_one_or_none()
    if not dc:
        raise HTTPException(status_code=404, detail="Data center not found")
    return dc


@router.get("/{datacenter_id}/overview", response_model=DataCenterOverview)
async def datacenter_overview(
    datacenter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    try:
        data = await get_datacenter_overview(db, datacenter_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Data center not found")
    return DataCenterOverview(**data)


@router.post("/{datacenter_id}/racks", response_model=RackResponse, status_code=status.HTTP_201_CREATED)
async def create_rack(
    datacenter_id: int,
    payload: RackCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DATACENTERS))],
):
    dc_result = await db.execute(select(DataCenter).where(DataCenter.id == datacenter_id))
    if not dc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Data center not found")

    rack = Rack(datacenter_id=datacenter_id, **payload.model_dump())
    db.add(rack)
    await db.flush()
    await db.refresh(rack)
    return rack


@router.get("/{datacenter_id}/racks", response_model=list[RackResponse])
async def list_racks(
    datacenter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(Rack).where(Rack.datacenter_id == datacenter_id))
    return list(result.scalars().all())
