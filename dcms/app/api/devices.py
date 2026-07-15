from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_permission
from app.database import get_db
from app.models import Device, DeviceCredential, Permission, ProtocolType, User, VendorType
from app.services.datacenter_overview import infer_device_type
from app.schemas import (
    DeviceCreate,
    DeviceResponse,
    DiscoverRequest,
    DiscoverResponse,
    DiscoveredDeviceResponse,
    ImportDiscoveredRequest,
    ImportDiscoveredResponse,
    PollResult,
)
from app.services.device_monitor import poll_all_devices, poll_device
from app.services.network_discovery import discover_network

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
        device_type=payload.device_type,
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


@router.post("/discover", response_model=DiscoverResponse)
async def discover_devices(
    payload: DiscoverRequest,
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    if not payload.cidr and not (payload.start_ip and payload.end_ip):
        raise HTTPException(status_code=400, detail="Provide cidr or start_ip + end_ip")

    try:
        from app.services.network_discovery import parse_ip_range

        host_count = len(parse_ip_range(payload.cidr, payload.start_ip, payload.end_ip))
        if host_count > payload.max_hosts:
            host_count = payload.max_hosts

        discovered = await discover_network(
            cidr=payload.cidr,
            start_ip=payload.start_ip,
            end_ip=payload.end_ip,
            community=payload.community,
            port=payload.port,
            max_hosts=payload.max_hosts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DiscoverResponse(
        scanned=host_count,
        found=len(discovered),
        devices=[DiscoveredDeviceResponse(**d.__dict__) for d in discovered],
    )


@router.post("/import-discovered", response_model=ImportDiscoveredResponse)
async def import_discovered_devices(
    payload: ImportDiscoveredRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    imported_ids: list[int] = []
    skipped = 0

    for ip in payload.ips:
        existing = await db.execute(select(Device).where(Device.ip_address == ip))
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        scan = await discover_network(start_ip=ip, end_ip=ip, community=payload.community, port=payload.port)
        if not scan:
            skipped += 1
            continue

        found = scan[0]
        vendor = found.vendor if found.vendor != VendorType.GENERIC else VendorType.CISCO
        device = Device(
            datacenter_id=payload.datacenter_id,
            name=found.hostname,
            hostname=found.hostname,
            ip_address=found.ip_address,
            vendor=vendor,
            device_type=infer_device_type(vendor, found.hostname, found.model),
            model=found.model,
        )
        db.add(device)
        await db.flush()
        db.add(
            DeviceCredential(
                device_id=device.id,
                protocol=ProtocolType.SNMP,
                community=payload.community,
                port=payload.port,
            )
        )
        imported_ids.append(device.id)

    if payload.poll_after_import:
        for device_id in imported_ids:
            await poll_device(db, device_id)

    return ImportDiscoveredResponse(imported=len(imported_ids), skipped=skipped, device_ids=imported_ids)


@router.post("/poll-all")
async def poll_all_devices_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    return await poll_all_devices(db)


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
