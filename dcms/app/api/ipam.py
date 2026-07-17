from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.database import get_db
from app.models import IpAddress, IpPrefix, Permission, User
from app.schemas import (
    IpAddressResponse,
    IpAddressUpdate,
    IpConflictItem,
    IpPrefixCreate,
    IpPrefixResponse,
    IpPrefixUpdate,
    IpPrefixUtilization,
    IpSyncResult,
)
from app.services.ipam import find_ip_conflicts, prefix_utilization, sync_prefix_addresses

router = APIRouter(prefix="/ipam", tags=["IPAM"])


@router.get("/prefixes", response_model=list[IpPrefixResponse])
async def list_prefixes(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = select(IpPrefix).order_by(IpPrefix.cidr)
    if datacenter_id:
        query = query.where(IpPrefix.datacenter_id == datacenter_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/prefixes", response_model=IpPrefixResponse, status_code=status.HTTP_201_CREATED)
async def create_prefix(
    payload: IpPrefixCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_IPAM))],
):
    prefix = IpPrefix(**payload.model_dump())
    db.add(prefix)
    await db.flush()
    await db.refresh(prefix)
    try:
        await sync_prefix_addresses(db, prefix.id)
    except Exception:
        pass
    return prefix


@router.get("/prefixes/{prefix_id}", response_model=IpPrefixResponse)
async def get_prefix(
    prefix_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(IpPrefix).where(IpPrefix.id == prefix_id))
    prefix = result.scalar_one_or_none()
    if not prefix:
        raise HTTPException(status_code=404, detail="Prefix not found")
    return prefix


@router.patch("/prefixes/{prefix_id}", response_model=IpPrefixResponse)
async def update_prefix(
    prefix_id: int,
    payload: IpPrefixUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_IPAM))],
):
    result = await db.execute(select(IpPrefix).where(IpPrefix.id == prefix_id))
    prefix = result.scalar_one_or_none()
    if not prefix:
        raise HTTPException(status_code=404, detail="Prefix not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefix, key, value)
    await db.flush()
    await db.refresh(prefix)
    return prefix


@router.delete("/prefixes/{prefix_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prefix(
    prefix_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_IPAM))],
):
    result = await db.execute(select(IpPrefix).where(IpPrefix.id == prefix_id))
    prefix = result.scalar_one_or_none()
    if not prefix:
        raise HTTPException(status_code=404, detail="Prefix not found")
    await db.delete(prefix)


@router.get("/prefixes/{prefix_id}/addresses", response_model=list[IpAddressResponse])
async def list_addresses(
    prefix_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    status_filter: str | None = None,
):
    query = select(IpAddress).where(IpAddress.prefix_id == prefix_id).order_by(IpAddress.address)
    if status_filter:
        query = query.where(IpAddress.status == status_filter)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.patch("/addresses/{address_id}", response_model=IpAddressResponse)
async def update_address(
    address_id: int,
    payload: IpAddressUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_IPAM))],
):
    result = await db.execute(select(IpAddress).where(IpAddress.id == address_id))
    addr = result.scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(addr, key, value)
    await db.flush()
    await db.refresh(addr)
    return addr


@router.post("/prefixes/{prefix_id}/sync", response_model=IpSyncResult)
async def sync_prefix(
    prefix_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_IPAM))],
):
    try:
        return await sync_prefix_addresses(db, prefix_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/prefixes/{prefix_id}/utilization", response_model=IpPrefixUtilization)
async def get_utilization(
    prefix_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    return await prefix_utilization(db, prefix_id)


@router.get("/conflicts", response_model=list[IpConflictItem])
async def get_conflicts(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    return await find_ip_conflicts(db, datacenter_id)
