from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_permission
from app.database import get_db
from app.models import Permission, Server, ServerCredential, User
from app.schemas import MonitoringGuide, ServerCreate, ServerPollResult, ServerResponse
from app.services.monitoring_guide import MONITORING_GUIDES
from app.services.server_monitor import poll_all_servers, poll_server

router = APIRouter(prefix="/servers", tags=["Servers"])


@router.get("/monitoring-guide", response_model=MonitoringGuide)
async def server_monitoring_guide(_: Annotated[User, Depends(require_permission(Permission.VIEW))]):
    return MonitoringGuide(**MONITORING_GUIDES["server"])


@router.get("", response_model=list[ServerResponse])
async def list_servers(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = select(Server).order_by(Server.name)
    if datacenter_id:
        query = query.where(Server.datacenter_id == datacenter_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: ServerCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_SERVERS))],
):
    server = Server(
        datacenter_id=payload.datacenter_id,
        rack_id=payload.rack_id,
        name=payload.name,
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        os_type=payload.os_type,
        server_role=payload.server_role,
        cpu_cores=payload.cpu_cores,
        ram_gb=payload.ram_gb,
        position_u=payload.position_u,
        notes=payload.notes,
    )
    db.add(server)
    await db.flush()
    for cred in payload.credentials:
        db.add(ServerCredential(server_id=server.id, **cred.model_dump()))
    await db.refresh(server)
    return server


@router.post("/poll-all")
async def poll_all_servers_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_SERVERS))],
):
    return await poll_all_servers(db)


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.get("/{server_id}/credentials")
async def get_server_credentials(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_SERVERS))],
):
    result = await db.execute(
        select(Server).options(selectinload(Server.credentials)).where(Server.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
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
        for c in server.credentials
    ]


@router.post("/{server_id}/poll", response_model=ServerPollResult)
async def poll_server_endpoint(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_SERVERS))],
):
    result = await poll_server(db, server_id)
    return ServerPollResult(**result)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_SERVERS))],
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    await db.delete(server)
