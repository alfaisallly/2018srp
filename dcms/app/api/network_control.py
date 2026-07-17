from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import require_permission
from app.database import get_db
from app.models import (
    BranchSite,
    ConfigTemplate,
    DataCenter,
    Device,
    DeviceType,
    DeviceVlan,
    FirewallRule,
    NetworkLink,
    Permission,
    SwitchPort,
    User,
    VendorType,
)
from app.schemas import (
    BranchSiteResponse,
    ConfigTemplateRenderRequest,
    ConfigTemplateRenderResponse,
    ConfigTemplateResponse,
    DeviceVlanResponse,
    FirewallRuleResponse,
    NetworkLinkResponse,
    NetworkOverviewResponse,
    SwitchDetailResponse,
    SwitchPortResponse,
    TopologyResponse,
)
from app.services.config_templates import render_template, validate_variables
from app.services.network_inventory import get_network_overview
from app.services.network_reports import generate_network_report
from app.services.switch_detail import get_switch_detail
from app.services.topology_builder import build_port_topology

router = APIRouter(prefix="/network", tags=["Network Control"])


@router.get("/overview", response_model=NetworkOverviewResponse)
async def network_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    data = await get_network_overview(db, datacenter_id)
    return NetworkOverviewResponse(**data)


@router.get("/devices", response_model=list[dict])
async def list_network_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
    device_type: DeviceType | None = None,
):
    query = select(Device).order_by(Device.name)
    if datacenter_id:
        query = query.where(Device.datacenter_id == datacenter_id)
    if device_type:
        query = query.where(Device.device_type == device_type)
    result = await db.execute(query)
    devices = list(result.scalars().all())
    return [
        {
            "id": d.id,
            "name": d.name,
            "hostname": d.hostname,
            "ip_address": d.ip_address,
            "vendor": d.vendor.value,
            "device_type": d.device_type.value if d.device_type else "other",
            "status": d.status.value,
            "datacenter_id": d.datacenter_id,
        }
        for d in devices
    ]


@router.get("/devices/{device_id}/detail", response_model=SwitchDetailResponse)
async def switch_detail(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    detail = await get_switch_detail(db, device_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Device not found")
    return SwitchDetailResponse(**detail)


@router.get("/devices/{device_id}/ports", response_model=list[SwitchPortResponse])
async def device_ports(
    device_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(
        select(SwitchPort)
        .where(SwitchPort.device_id == device_id)
        .options(selectinload(SwitchPort.connected_device))
        .order_by(SwitchPort.port_index, SwitchPort.name)
    )
    ports = list(result.scalars().all())
    return [
        SwitchPortResponse(
            id=p.id,
            device_id=p.device_id,
            name=p.name,
            port_index=p.port_index,
            description=p.description,
            oper_status=p.oper_status.value,
            admin_status=p.admin_status,
            speed_mbps=p.speed_mbps,
            duplex=p.duplex,
            vlan_mode=p.vlan_mode,
            access_vlan=p.access_vlan,
            trunk_vlans=p.trunk_vlans,
            connected_device_id=p.connected_device_id,
            connected_device_name=p.connected_device.name if p.connected_device else None,
            connected_port_name=p.connected_port_name,
            link_type=p.link_type.value if p.link_type else None,
            ip_address=p.ip_address,
            services=p.services,
            settings=p.settings,
            last_sync_at=p.last_sync_at,
        )
        for p in ports
    ]


@router.get("/vlans", response_model=list[DeviceVlanResponse])
async def list_vlans(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
    device_id: int | None = None,
):
    query = select(DeviceVlan).options(selectinload(DeviceVlan.device)).order_by(DeviceVlan.vlan_id)
    if datacenter_id:
        query = query.where(DeviceVlan.datacenter_id == datacenter_id)
    if device_id:
        query = query.where(DeviceVlan.device_id == device_id)
    result = await db.execute(query)
    vlans = list(result.scalars().all())
    return [
        DeviceVlanResponse(
            id=v.id,
            datacenter_id=v.datacenter_id,
            device_id=v.device_id,
            device_name=v.device.name if v.device else None,
            vlan_id=v.vlan_id,
            name=v.name,
            subnet=v.subnet,
            gateway=v.gateway,
            status=v.status,
            description=v.description,
            port_count=v.port_count,
        )
        for v in vlans
    ]


@router.get("/links", response_model=list[NetworkLinkResponse])
async def list_links(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = (
        select(NetworkLink)
        .options(selectinload(NetworkLink.from_device), selectinload(NetworkLink.to_device))
        .order_by(NetworkLink.id)
    )
    if datacenter_id:
        query = query.where(NetworkLink.datacenter_id == datacenter_id)
    result = await db.execute(query)
    links = list(result.scalars().all())
    return [
        NetworkLinkResponse(
            id=l.id,
            datacenter_id=l.datacenter_id,
            from_device_id=l.from_device_id,
            from_device_name=l.from_device.name,
            from_port=l.from_port,
            to_device_id=l.to_device_id,
            to_device_name=l.to_device.name,
            to_port=l.to_port,
            link_type=l.link_type.value,
            is_primary=l.is_primary,
            bandwidth_mbps=l.bandwidth_mbps,
            status=l.status,
            description=l.description,
        )
        for l in links
    ]


@router.get("/firewall", response_model=list[FirewallRuleResponse])
async def list_firewall_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
    device_id: int | None = None,
):
    query = select(FirewallRule).options(selectinload(FirewallRule.device)).order_by(FirewallRule.order_index)
    if device_id:
        query = query.where(FirewallRule.device_id == device_id)
    elif datacenter_id:
        query = query.join(Device).where(Device.datacenter_id == datacenter_id)
    result = await db.execute(query)
    rules = list(result.scalars().all())
    return [
        FirewallRuleResponse(
            id=r.id,
            device_id=r.device_id,
            device_name=r.device.name,
            rule_id=r.rule_id,
            name=r.name,
            action=r.action.value,
            source=r.source,
            destination=r.destination,
            service=r.service,
            protocol=r.protocol,
            port=r.port,
            zone_in=r.zone_in,
            zone_out=r.zone_out,
            enabled=r.enabled,
            hit_count=r.hit_count,
            order_index=r.order_index,
        )
        for r in rules
    ]


@router.get("/branches", response_model=list[BranchSiteResponse])
async def list_branch_sites(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    datacenter_id: int | None = None,
):
    query = (
        select(BranchSite)
        .options(selectinload(BranchSite.primary_device), selectinload(BranchSite.backup_device))
        .order_by(BranchSite.name)
    )
    if datacenter_id:
        query = query.where(BranchSite.datacenter_id == datacenter_id)
    result = await db.execute(query)
    branches = list(result.scalars().all())
    return [
        BranchSiteResponse(
            id=b.id,
            datacenter_id=b.datacenter_id,
            name=b.name,
            location=b.location,
            address=b.address,
            primary_device_id=b.primary_device_id,
            primary_device_name=b.primary_device.name if b.primary_device else None,
            primary_port=b.primary_port,
            primary_link_type=b.primary_link_type.value,
            backup_enabled=b.backup_enabled,
            backup_link_type=b.backup_link_type.value if b.backup_link_type else None,
            backup_device_id=b.backup_device_id,
            backup_device_name=b.backup_device.name if b.backup_device else None,
            backup_port=b.backup_port,
            backup_wireless_ssid=b.backup_wireless_ssid,
            status=b.status,
            notes=b.notes,
        )
        for b in branches
    ]


@router.get("/topology/{datacenter_id}", response_model=TopologyResponse)
async def port_topology(
    datacenter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    dc_result = await db.execute(select(DataCenter).where(DataCenter.id == datacenter_id))
    if not dc_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Datacenter not found")
    topo = await build_port_topology(db, datacenter_id)
    return TopologyResponse(**topo)


@router.get("/reports/{datacenter_id}")
async def network_report(
    datacenter_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW_REPORTS))],
):
    try:
        content = await generate_network_report(db, datacenter_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    media_type = "application/pdf" if content[:4] == b"%PDF" else "text/html"
    filename = "network-report.pdf" if media_type == "application/pdf" else "network-report.html"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/config-templates", response_model=list[ConfigTemplateResponse])
async def list_config_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
    vendor: VendorType | None = None,
    category: str | None = None,
):
    query = select(ConfigTemplate).order_by(ConfigTemplate.vendor, ConfigTemplate.category, ConfigTemplate.name)
    if vendor:
        query = query.where(ConfigTemplate.vendor == vendor)
    if category:
        query = query.where(ConfigTemplate.category == category)
    result = await db.execute(query)
    templates = list(result.scalars().all())
    return [ConfigTemplateResponse.model_validate(t) for t in templates]


@router.get("/config-templates/{template_id}", response_model=ConfigTemplateResponse)
async def get_config_template(
    template_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.VIEW))],
):
    result = await db.execute(select(ConfigTemplate).where(ConfigTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return ConfigTemplateResponse.model_validate(template)


@router.post("/config-templates/{template_id}/render", response_model=ConfigTemplateRenderResponse)
async def render_config_template(
    template_id: int,
    payload: ConfigTemplateRenderRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_permission(Permission.MANAGE_DEVICES))],
):
    result = await db.execute(select(ConfigTemplate).where(ConfigTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    errors = validate_variables(template, payload.variables)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)

    try:
        config = render_template(template.template_body, payload.variables, template.variables)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Render error: {e}") from e

    return ConfigTemplateRenderResponse(
        template_id=template.id,
        template_name=template.name,
        vendor=template.vendor.value,
        config=config,
    )
