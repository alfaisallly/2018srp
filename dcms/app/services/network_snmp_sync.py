"""Collect switch/router inventory via SNMP for transport networks."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Device,
    DeviceType,
    DeviceVlan,
    LinkType,
    PortOperStatus,
    ProtocolType,
    SwitchPort,
    VendorType,
)
from app.services.snmp_collector import snmp_walk
from app.services.snmp_inventory import (
    build_inventory,
    parse_cdp_neighbors,
    parse_cisco_port_vlans,
    parse_dot1q_vlans,
    parse_if_table,
    parse_lldp_neighbors,
)
from app.services.switch_detail import _build_port_settings

NETWORK_SEGMENTS = {
    "transport_branch": "نقل — مواقع فرعية ↔ مركز البيانات",
    "transport_dc": "نقل — بين مراكز البيانات",
    "internal": "داخلية — مركز البيانات",
}


def get_network_segment(device: Device) -> str:
    tags = device.tags or {}
    return tags.get("network_segment", "internal")


def is_snmp_inventory_eligible(device: Device) -> bool:
    segment = get_network_segment(device)
    tags = device.tags or {}
    if tags.get("snmp_inventory") is False:
        return False
    if segment in ("transport_branch", "transport_dc"):
        return True
    return bool(tags.get("snmp_inventory"))


async def collect_snmp_inventory(
    host: str,
    community: str,
    vendor: VendorType,
    port: int = 161,
) -> dict:
    def _collect() -> dict:
        if_table: dict[str, str] = {}
        for base in (
            "1.3.6.1.2.1.2.2.1.2",
            "1.3.6.1.2.1.2.2.1.3",
            "1.3.6.1.2.1.2.2.1.4",
            "1.3.6.1.2.1.2.2.1.5",
            "1.3.6.1.2.1.2.2.1.7",
            "1.3.6.1.2.1.2.2.1.8",
            "1.3.6.1.2.1.31.1.1.1.15",
        ):
            if_table.update(snmp_walk(host, community, base, port, max_rows=256))

        if not if_table:
            return {"ok": False, "error": "No SNMP interface data (timeout or wrong community)"}

        if_rows = parse_if_table(if_table)
        vlan_walk = snmp_walk(host, community, "1.3.6.1.2.1.17.7.1.4.3.1.1", port, max_rows=128)
        vlans = parse_dot1q_vlans(vlan_walk)

        port_vlans: dict[int, int] = {}
        if vendor == VendorType.CISCO:
            cisco_vlan_walk = snmp_walk(host, community, "1.3.6.1.4.1.9.9.68.1.2.2.1.2", port, max_rows=256)
            port_vlans = parse_cisco_port_vlans(cisco_vlan_walk)

        neighbors: dict[int, dict] = {}
        if vendor == VendorType.CISCO:
            cdp_walk: dict[str, str] = {}
            for base in ("1.3.6.1.4.1.9.9.23.1.2.1.1.6", "1.3.6.1.4.1.9.9.23.1.2.1.1.7"):
                cdp_walk.update(snmp_walk(host, community, base, port, max_rows=256))
            neighbors = parse_cdp_neighbors(cdp_walk)
        elif vendor == VendorType.JUNIPER:
            lldp_walk: dict[str, str] = {}
            for base in ("1.0.8802.1.1.2.1.4.1.1.9", "1.0.8802.1.1.2.1.4.2.1.7"):
                lldp_walk.update(snmp_walk(host, community, base, port, max_rows=256))
            neighbors = parse_lldp_neighbors(lldp_walk)

        inventory = build_inventory(if_rows, neighbors, vlans, port_vlans)
        return {
            "ok": True,
            "interfaces": len(inventory.interfaces),
            "vlans": len(inventory.vlans),
            "inventory": inventory,
        }

    return await asyncio.to_thread(_collect)


async def _resolve_peer_device(session: AsyncSession, datacenter_id: int, hostname: str | None) -> Device | None:
    if not hostname:
        return None
    clean = hostname.split(".")[0].strip().lower()
    result = await session.execute(
        select(Device).where(
            Device.datacenter_id == datacenter_id,
            or_(
                Device.hostname.ilike(clean),
                Device.name.ilike(clean),
                Device.hostname.ilike(f"{clean}%"),
                Device.name.ilike(f"{clean}%"),
            ),
        )
    )
    return result.scalar_one_or_none()


async def sync_device_snmp_inventory(session: AsyncSession, device_id: int) -> dict:
    result = await session.execute(
        select(Device)
        .where(Device.id == device_id)
        .options(selectinload(Device.credentials))
    )
    device = result.scalar_one_or_none()
    if not device:
        return {"ok": False, "error": "Device not found"}

    if device.device_type not in (DeviceType.SWITCH, DeviceType.ROUTER, DeviceType.FIREWALL, None):
        return {"ok": False, "error": "SNMP inventory applies to switches/routers/firewalls only"}

    snmp_cred = next((c for c in device.credentials if c.protocol == ProtocolType.SNMP and c.community), None)
    if not snmp_cred:
        return {"ok": False, "error": "No SNMP credentials configured for this device"}

    collected = await collect_snmp_inventory(
        device.ip_address,
        snmp_cred.community,
        device.vendor,
        snmp_cred.port or 161,
    )
    if not collected.get("ok"):
        return collected

    inventory = collected["inventory"]
    now = datetime.now(timezone.utc)

    existing_ports = await session.execute(select(SwitchPort).where(SwitchPort.device_id == device.id))
    port_by_name = {p.name: p for p in existing_ports.scalars().all()}

    ports_updated = 0
    ports_created = 0
    for iface in inventory.interfaces:
        oper = PortOperStatus.UP if iface.oper_status == "up" else PortOperStatus.DOWN
        settings = _build_port_settings(
            iface.speed_mbps,
            iface.oper_status,
            {
                "mtu": iface.mtu or 1500,
                "source": "snmp",
                "synced_at": now.isoformat(),
            },
        )
        peer = await _resolve_peer_device(session, device.datacenter_id, iface.neighbor_hostname)
        existing = port_by_name.get(iface.name)
        if existing:
            existing.port_index = iface.if_index
            existing.oper_status = oper
            existing.admin_status = iface.admin_status
            existing.speed_mbps = iface.speed_mbps
            existing.access_vlan = iface.access_vlan
            existing.vlan_mode = iface.vlan_mode if iface.access_vlan else existing.vlan_mode
            existing.connected_device_id = peer.id if peer else existing.connected_device_id
            existing.connected_port_name = iface.neighbor_port or existing.connected_port_name
            existing.settings = settings
            existing.last_sync_at = now
            ports_updated += 1
        else:
            session.add(
                SwitchPort(
                    device_id=device.id,
                    name=iface.name,
                    port_index=iface.if_index,
                    oper_status=oper,
                    admin_status=iface.admin_status,
                    speed_mbps=iface.speed_mbps,
                    vlan_mode=iface.vlan_mode,
                    access_vlan=iface.access_vlan,
                    connected_device_id=peer.id if peer else None,
                    connected_port_name=iface.neighbor_port,
                    link_type=LinkType.FIBER if iface.speed_mbps >= 10000 else LinkType.COPPER,
                    settings=settings,
                    last_sync_at=now,
                )
            )
            ports_created += 1

    vlans_created = 0
    for vlan in inventory.vlans:
        existing_vlan = await session.execute(
            select(DeviceVlan).where(
                DeviceVlan.datacenter_id == device.datacenter_id,
                DeviceVlan.device_id == device.id,
                DeviceVlan.vlan_id == vlan.vlan_id,
            )
        )
        if existing_vlan.scalar_one_or_none():
            continue
        session.add(
            DeviceVlan(
                datacenter_id=device.datacenter_id,
                device_id=device.id,
                vlan_id=vlan.vlan_id,
                name=vlan.name,
                status="active",
                description=f"SNMP sync — {NETWORK_SEGMENTS.get(get_network_segment(device), '')}",
            )
        )
        vlans_created += 1

    segment = get_network_segment(device)
    return {
        "ok": True,
        "device": device.name,
        "network_segment": segment,
        "network_segment_label": NETWORK_SEGMENTS.get(segment, segment),
        "ports_created": ports_created,
        "ports_updated": ports_updated,
        "vlans_created": vlans_created,
        "interfaces_found": len(inventory.interfaces),
        "source": "snmp",
    }


async def sync_transport_devices(session: AsyncSession, datacenter_id: int | None = None) -> dict:
    query = select(Device).options(selectinload(Device.credentials))
    if datacenter_id:
        query = query.where(Device.datacenter_id == datacenter_id)
    result = await session.execute(query)
    devices = [d for d in result.scalars().all() if is_snmp_inventory_eligible(d)]

    results = []
    for device in devices:
        sync_result = await sync_device_snmp_inventory(session, device.id)
        results.append({"device_id": device.id, **sync_result})

    ok_count = sum(1 for r in results if r.get("ok"))
    return {
        "eligible": len(devices),
        "success": ok_count,
        "failed": len(devices) - ok_count,
        "results": results,
    }
