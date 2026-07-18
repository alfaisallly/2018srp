from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.database import get_db
from app.models import IntegrationEndpoint, Permission, User
from app.schemas import IntegrationCreate, IntegrationResponse, IntegrationTestResult, IntegrationUpdate
from app.services.integration_sync import sync_all_integrations, sync_integration, test_integration

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = select(IntegrationEndpoint).order_by(IntegrationEndpoint.name)
    if datacenter_id:
        query = query.where(IntegrationEndpoint.datacenter_id == datacenter_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: IntegrationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_INTEGRATIONS))],
):
    endpoint = IntegrationEndpoint(**payload.model_dump())
    db.add(endpoint)
    await db.flush()
    await db.refresh(endpoint)
    return endpoint


@router.get("/{endpoint_id}", response_model=IntegrationResponse)
async def get_integration(
    endpoint_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(IntegrationEndpoint).where(IntegrationEndpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Integration not found")
    return endpoint


@router.patch("/{endpoint_id}", response_model=IntegrationResponse)
async def update_integration(
    endpoint_id: int,
    payload: IntegrationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_INTEGRATIONS))],
):
    result = await db.execute(select(IntegrationEndpoint).where(IntegrationEndpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Integration not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(endpoint, key, value)
    await db.flush()
    await db.refresh(endpoint)
    return endpoint


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    endpoint_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_INTEGRATIONS))],
):
    result = await db.execute(select(IntegrationEndpoint).where(IntegrationEndpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Integration not found")
    await db.delete(endpoint)


@router.post("/{endpoint_id}/test", response_model=IntegrationTestResult)
async def test_endpoint(
    endpoint_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_INTEGRATIONS))],
):
    try:
        result = await test_integration(db, endpoint_id)
        return IntegrationTestResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{endpoint_id}/sync")
async def sync_endpoint(
    endpoint_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_INTEGRATIONS))],
):
    try:
        return await sync_integration(db, endpoint_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync-all")
async def sync_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_INTEGRATIONS))],
):
    return await sync_all_integrations(db)
