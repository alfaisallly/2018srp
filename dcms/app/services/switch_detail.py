"""Detailed switch/device profile: ports, VLANs, capacity, peers, and firewall context."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    DataCenter,
    Device,
    DeviceType,
    DeviceVlan,
    FirewallRule,
    NetworkLink,
    PortOperStatus,
    SwitchPort,
)
from app.services.topology_builder import LINK_LABELS, VENDOR_COLORS

MTU_DEFAULT = 1500
MIN_FRAME_BYTES = 64
AVG_FRAME_BYTES = 512


def _pps_capacity_mbps(speed_mbps: int, frame_bytes: int = MIN_FRAME_BYTES) -> int:
    if not speed_mbps or frame_bytes <= 0:
        return 0
    return int(speed_mbps * 1_000_000 / (frame_bytes * 8))


def _build_port_settings(speed_mbps: int | None, oper_status: str, existing: dict | None = None) -> dict:
    settings = dict(existing or {})
    speed = speed_mbps or 1000
    util = settings.get("utilization_pct")
    if util is None:
        util = 35 if oper_status == "up" else 0
    used_mbps = round(speed * util / 100, 1)
    settings.setdefault("mtu", MTU_DEFAULT)
    settings.setdefault("utilization_pct", util)
    settings.setdefault("used_mbps", used_mbps)
    settings.setdefault("max_pps", _pps_capacity_mbps(speed, MIN_FRAME_BYTES))
    settings.setdefault("avg_pps", int(used_mbps * 1_000_000 / (AVG_FRAME_BYTES * 8)) if used_mbps else 0)
    settings.setdefault("duplex_config", settings.get("duplex_config", "full"))
    settings.setdefault("storm_control", settings.get("storm_control", True))
    settings.setdefault("portfast", settings.get("portfast", False))
    return settings


def _vlan_label(vlan_id: int, vlan_map: dict[int, DeviceVlan]) -> str:
    v = vlan_map.get(vlan_id)
    if v:
        return f"VLAN {vlan_id} ({v.name})"
    return f"VLAN {vlan_id}"


def _port_vlan_display(port: SwitchPort, vlan_map: dict[int, DeviceVlan]) -> dict:
    if port.vlan_mode == "access" and port.access_vlan:
        return {
            "mode": "access",
            "vlan_ids": [port.access_vlan],
            "vlan_labels": [_vlan_label(port.access_vlan, vlan_map)],
            "summary": _vlan_label(port.access_vlan, vlan_map),
        }
    trunk_ids = port.trunk_vlans or []
    labels = [_vlan_label(vid, vlan_map) for vid in trunk_ids]
    return {
        "mode": "trunk",
        "vlan_ids": trunk_ids,
        "vlan_labels": labels,
        "summary": ", ".join(str(v) for v in trunk_ids) if trunk_ids else "—",
    }


async def get_switch_detail(session: AsyncSession, device_id: int) -> dict | None:
    device_result = await session.execute(
        select(Device)
        .where(Device.id == device_id)
        .options(selectinload(Device.datacenter))
    )
    device = device_result.scalar_one_or_none()
    if not device:
        return None

    dc_result = await session.execute(select(DataCenter).where(DataCenter.id == device.datacenter_id))
    datacenter = dc_result.scalar_one_or_none()

    ports_result = await session.execute(
        select(SwitchPort)
        .where(SwitchPort.device_id == device_id)
        .options(selectinload(SwitchPort.connected_device))
        .order_by(SwitchPort.port_index, SwitchPort.name)
    )
    ports = list(ports_result.scalars().all())

    vlans_result = await session.execute(
        select(DeviceVlan).where(
            DeviceVlan.datacenter_id == device.datacenter_id,
            or_(DeviceVlan.device_id == device_id, DeviceVlan.device_id.is_(None)),
        )
    )
    vlans = list(vlans_result.scalars().all())
    vlan_map = {v.vlan_id: v for v in vlans}

    vlan_port_counts: dict[int, list[str]] = {}
    for port in ports:
        info = _port_vlan_display(port, vlan_map)
        for vid in info["vlan_ids"]:
            vlan_port_counts.setdefault(vid, []).append(port.name)

    vlan_details = []
    for v in sorted(vlans, key=lambda x: x.vlan_id):
        port_names = vlan_port_counts.get(v.vlan_id, [])
        vlan_details.append({
            "id": v.id,
            "vlan_id": v.vlan_id,
            "name": v.name,
            "subnet": v.subnet,
            "gateway": v.gateway,
            "status": v.status,
            "description": v.description,
            "ports": port_names,
            "port_count": len(port_names),
        })

    links_result = await session.execute(
        select(NetworkLink)
        .where(
            NetworkLink.datacenter_id == device.datacenter_id,
            or_(NetworkLink.from_device_id == device_id, NetworkLink.to_device_id == device_id),
        )
        .options(selectinload(NetworkLink.from_device), selectinload(NetworkLink.to_device))
    )
    links = list(links_result.scalars().all())

    peer_ids: set[int] = set()
    link_details = []
    for link in links:
        if link.from_device_id == device_id:
            peer = link.to_device
            peer_ids.add(link.to_device_id)
            local_port, remote_port = link.from_port, link.to_port
            direction = "outbound"
        else:
            peer = link.from_device
            peer_ids.add(link.from_device_id)
            local_port, remote_port = link.to_port, link.from_port
            direction = "inbound"
        link_details.append({
            "id": link.id,
            "direction": direction,
            "local_port": local_port,
            "peer_device_id": peer.id,
            "peer_device_name": peer.name,
            "peer_device_type": peer.device_type.value if peer.device_type else "other",
            "peer_port": remote_port,
            "link_type": link.link_type.value,
            "link_type_label": LINK_LABELS.get(link.link_type, link.link_type.value),
            "bandwidth_mbps": link.bandwidth_mbps,
            "is_primary": link.is_primary,
            "status": link.status,
        })

    port_details = []
    speeds: list[int] = []
    total_capacity = 0
    active_capacity = 0
    used_capacity = 0.0
    total_pps = 0
    max_pps_capacity = 0

    for port in ports:
        speed = port.speed_mbps or 1000
        speeds.append(speed)
        total_capacity += speed
        settings = _build_port_settings(port.speed_mbps, port.oper_status.value, port.settings)
        if port.oper_status == PortOperStatus.UP:
            active_capacity += speed
            used_capacity += settings.get("used_mbps", 0)
            total_pps += settings.get("avg_pps", 0)
        max_pps_capacity += settings.get("max_pps", 0)

        vlan_info = _port_vlan_display(port, vlan_map)
        peer = None
        if port.connected_device:
            peer = {
                "device_id": port.connected_device.id,
                "device_name": port.connected_device.name,
                "device_type": port.connected_device.device_type.value if port.connected_device.device_type else "other",
                "port_name": port.connected_port_name,
                "ip_address": port.connected_device.ip_address,
            }
            peer_ids.add(port.connected_device.id)

        port_details.append({
            "id": port.id,
            "name": port.name,
            "port_index": port.port_index,
            "description": port.description,
            "oper_status": port.oper_status.value,
            "admin_status": port.admin_status,
            "speed_mbps": speed,
            "duplex": port.duplex or settings.get("duplex_config", "full"),
            "vlan_mode": port.vlan_mode,
            "vlan_info": vlan_info,
            "ip_address": port.ip_address,
            "services": port.services or [],
            "link_type": port.link_type.value if port.link_type else None,
            "link_type_label": LINK_LABELS.get(port.link_type, "") if port.link_type else None,
            "peer": peer,
            "settings": settings,
        })

    min_speed = min(speeds) if speeds else 0
    max_speed = max(speeds) if speeds else 0
    bandwidth_util = round(used_capacity / total_capacity * 100, 1) if total_capacity else 0
    pps_util = round(total_pps / max_pps_capacity * 100, 1) if max_pps_capacity else 0

    capacity = {
        "total_ports": len(ports),
        "ports_up": sum(1 for p in ports if p.oper_status == PortOperStatus.UP),
        "ports_down": sum(1 for p in ports if p.oper_status != PortOperStatus.UP),
        "total_capacity_mbps": total_capacity,
        "active_capacity_mbps": active_capacity,
        "used_capacity_mbps": round(used_capacity, 1),
        "available_capacity_mbps": round(max(active_capacity - used_capacity, 0), 1),
        "min_port_mbps": min_speed,
        "max_port_mbps": max_speed,
        "bandwidth_utilization_pct": bandwidth_util,
        "total_packets_per_sec": total_pps,
        "max_packets_per_sec": max_pps_capacity,
        "packets_utilization_pct": pps_util,
        "mtu": MTU_DEFAULT,
    }

    firewall_rules: list[dict] = []
    seen_rule_ids: set[int] = set()
    if device.device_type == DeviceType.FIREWALL:
        fw_result = await session.execute(
            select(FirewallRule)
            .where(FirewallRule.device_id == device_id)
            .order_by(FirewallRule.order_index)
        )
        for r in fw_result.scalars().all():
            firewall_rules.append(_rule_dict(r, device.name, "local"))
            seen_rule_ids.add(r.id)

    peer_firewall_ids = set()
    if peer_ids:
        peers_result = await session.execute(
            select(Device).where(Device.id.in_(peer_ids))
        )
        for peer_dev in peers_result.scalars().all():
            if peer_dev.device_type == DeviceType.FIREWALL:
                peer_firewall_ids.add(peer_dev.id)

    if device.device_type != DeviceType.FIREWALL:
        fw_result = await session.execute(
            select(FirewallRule)
            .join(Device)
            .where(Device.datacenter_id == device.datacenter_id)
            .options(selectinload(FirewallRule.device))
            .order_by(FirewallRule.order_index)
        )
        for r in fw_result.scalars().all():
            if r.id in seen_rule_ids:
                continue
            if r.device_id in peer_firewall_ids or _rule_relates_to_device(r, device, vlan_map):
                firewall_rules.append(_rule_dict(r, r.device.name, "related"))
                seen_rule_ids.add(r.id)

    topology_nodes = [{
        "id": f"dev-{device.id}",
        "label": device.name,
        "shape": "box",
        "color": VENDOR_COLORS.get(device.vendor.value, "#94a3b8"),
        "fixed": {"x": 0, "y": 0},
    }]
    topology_edges = []
    if peer_ids:
        peers_result = await session.execute(select(Device).where(Device.id.in_(peer_ids)))
        peer_devices = list(peers_result.scalars().all())
        import math

        for i, peer_dev in enumerate(peer_devices):
            angle = (2 * math.pi * i) / max(len(peer_devices), 1)
            topology_nodes.append({
                "id": f"dev-{peer_dev.id}",
                "label": peer_dev.name,
                "color": VENDOR_COLORS.get(peer_dev.vendor.value, "#94a3b8"),
                "x": 250 * math.cos(angle),
                "y": 250 * math.sin(angle),
            })
        for ld in link_details:
            topology_edges.append({
                "from": f"dev-{device.id}",
                "to": f"dev-{ld['peer_device_id']}",
                "label": f"{ld['local_port']} ↔ {ld['peer_port']}",
                "title": ld["link_type_label"],
            })

    peers_summary = []
    if peer_ids:
        peers_result = await session.execute(select(Device).where(Device.id.in_(peer_ids)))
        for p in peers_result.scalars().all():
            connected_ports = [
                pd for pd in port_details
                if pd.get("peer") and pd["peer"]["device_id"] == p.id
            ]
            peers_summary.append({
                "device_id": p.id,
                "name": p.name,
                "ip_address": p.ip_address,
                "device_type": p.device_type.value if p.device_type else "other",
                "vendor": p.vendor.value,
                "status": p.status.value,
                "ports": [
                    {"local": cp["name"], "remote": cp["peer"]["port_name"], "link_type": cp.get("link_type_label")}
                    for cp in connected_ports
                ],
            })

    dtype = device.device_type.value if device.device_type else "other"
    segment = (device.tags or {}).get("network_segment", "internal")
    from app.services.network_snmp_sync import NETWORK_SEGMENTS, is_snmp_inventory_eligible

    return {
        "device": {
            "id": device.id,
            "name": device.name,
            "hostname": device.hostname,
            "ip_address": device.ip_address,
            "vendor": device.vendor.value,
            "device_type": dtype,
            "model": device.model,
            "status": device.status.value,
            "datacenter_id": device.datacenter_id,
            "datacenter_name": datacenter.name if datacenter else None,
            "network_segment": segment,
            "network_segment_label": NETWORK_SEGMENTS.get(segment, segment),
            "snmp_inventory": is_snmp_inventory_eligible(device),
            "tags": device.tags or {},
        },
        "capacity": capacity,
        "ports": port_details,
        "vlans": vlan_details,
        "links": link_details,
        "peers": peers_summary,
        "firewall_rules": firewall_rules,
        "local_topology": {"nodes": topology_nodes, "edges": topology_edges},
        "insights": _build_insights(device, capacity, port_details, vlan_details, peers_summary),
    }


def _rule_dict(rule: FirewallRule, device_name: str, scope: str) -> dict:
    return {
        "id": rule.id,
        "device_id": rule.device_id,
        "device_name": device_name,
        "scope": scope,
        "rule_id": rule.rule_id,
        "name": rule.name,
        "action": rule.action.value,
        "source": rule.source,
        "destination": rule.destination,
        "service": rule.service,
        "zone_in": rule.zone_in,
        "zone_out": rule.zone_out,
        "enabled": rule.enabled,
        "hit_count": rule.hit_count,
    }


def _rule_relates_to_device(rule: FirewallRule, device: Device, vlan_map: dict[int, DeviceVlan]) -> bool:
    targets = {device.ip_address}
    for v in vlan_map.values():
        if v.subnet:
            targets.add(v.subnet)
        if v.gateway:
            targets.add(v.gateway)
    text = f"{rule.source or ''} {rule.destination or ''} {rule.service or ''}"
    return any(t in text for t in targets if t)


def _build_insights(device, capacity, ports, vlans, peers) -> list[str]:
    insights = []
    if capacity["ports_down"] > 0:
        insights.append(f"يوجد {capacity['ports_down']} منفذ/منافذ غير نشطة — راجع الكابلات أو الإعدادات.")
    if capacity["bandwidth_utilization_pct"] > 75:
        insights.append(f"استخدام النطاق الترددي مرتفع ({capacity['bandwidth_utilization_pct']}%) — قد تحتاج ترقية الروابط.")
    elif capacity["bandwidth_utilization_pct"] < 20 and capacity["ports_up"] > 0:
        insights.append(f"السعة متاحة بشكل جيد — الاستخدام الحالي {capacity['bandwidth_utilization_pct']}%.")
    trunk_ports = [p for p in ports if p["vlan_mode"] == "trunk"]
    if trunk_ports:
        insights.append(f"{len(trunk_ports)} منفذ Trunk يربط VLANs متعددة بين الأجهزة.")
    if peers:
        fw_peers = [p for p in peers if p["device_type"] == "firewall"]
        if fw_peers:
            insights.append(f"مرتبط بـ {len(fw_peers)} جدار/جدران حماية — راجع قواعد Firewall المرتبطة.")
    if device.device_type == DeviceType.SWITCH and len(vlans) > 1:
        insights.append(f"السويج يخدم {len(vlans)} VLAN — العزل بين الشبكات مفعّل.")
    return insights
