from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.database import get_db
from app.models import NetworkMap, Permission, User
from app.schemas import NetworkMapCreate, NetworkMapResponse

router = APIRouter(prefix="/network-maps", tags=["Network Maps"])


@router.get("", response_model=list[NetworkMapResponse])
async def list_network_maps(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = select(NetworkMap).order_by(NetworkMap.name)
    if datacenter_id:
        query = query.where(NetworkMap.datacenter_id == datacenter_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=NetworkMapResponse, status_code=status.HTTP_201_CREATED)
async def create_network_map(
    payload: NetworkMapCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_NETWORK_MAPS))],
):
    network_map = NetworkMap(**payload.model_dump())
    db.add(network_map)
    await db.flush()
    await db.refresh(network_map)
    return network_map


@router.get("/{map_id}", response_model=NetworkMapResponse)
async def get_network_map(
    map_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(NetworkMap).where(NetworkMap.id == map_id))
    network_map = result.scalar_one_or_none()
    if not network_map:
        raise HTTPException(status_code=404, detail="Network map not found")
    return network_map


@router.put("/{map_id}", response_model=NetworkMapResponse)
async def update_network_map(
    map_id: int,
    payload: NetworkMapCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_NETWORK_MAPS))],
):
    result = await db.execute(select(NetworkMap).where(NetworkMap.id == map_id))
    network_map = result.scalar_one_or_none()
    if not network_map:
        raise HTTPException(status_code=404, detail="Network map not found")

    for key, value in payload.model_dump().items():
        setattr(network_map, key, value)
    await db.flush()
    await db.refresh(network_map)
    return network_map
