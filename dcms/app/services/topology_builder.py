"""Build port-level network topology diagrams from links and device inventory."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BranchSite, Device, DeviceType, LinkType, NetworkLink, SwitchPort

LINK_COLORS = {
    LinkType.FIBER: "#06b6d4",
    LinkType.COPPER: "#64748b",
    LinkType.WIRELESS: "#a855f7",
    LinkType.BACKUP: "#f59e0b",
    LinkType.LOGICAL: "#94a3b8",
}

LINK_LABELS = {
    LinkType.FIBER: "كابل ضوئي",
    LinkType.COPPER: "نحاسي",
    LinkType.WIRELESS: "لاسلكي",
    LinkType.BACKUP: "احتياطي",
    LinkType.LOGICAL: "منطقي",
}

VENDOR_COLORS = {
    "cisco": "#049fd9",
    "juniper": "#84bd00",
    "fortinet": "#ee3124",
    "generic": "#94a3b8",
}


def _device_node(device: Device) -> dict:
    dtype = device.device_type.value if device.device_type else "switch"
    shapes = {"switch": "box", "router": "diamond", "firewall": "triangle", "other": "dot"}
    return {
        "id": f"dev-{device.id}",
        "label": f"{device.name}\n{device.ip_address}",
        "shape": shapes.get(dtype, "box"),
        "color": VENDOR_COLORS.get(device.vendor.value, VENDOR_COLORS["generic"]),
        "title": f"{device.name} | {device.ip_address} | {dtype}",
        "group": dtype,
    }


def _link_edge(link: NetworkLink, devices: dict[int, Device]) -> dict:
    from_dev = devices.get(link.from_device_id)
    to_dev = devices.get(link.to_device_id)
    link_label = LINK_LABELS.get(link.link_type, link.link_type.value)
    port_label = f"{link.from_port} ↔ {link.to_port}"
    primary = "أساسي" if link.is_primary else "احتياطي"
    return {
        "id": f"link-{link.id}",
        "from": f"dev-{link.from_device_id}",
        "to": f"dev-{link.to_device_id}",
        "label": f"{port_label}\n{link_label} ({primary})",
        "title": f"{from_dev.name if from_dev else '?'}:{link.from_port} → {to_dev.name if to_dev else '?'}:{link.to_port}",
        "color": {"color": LINK_COLORS.get(link.link_type, "#475569")},
        "width": 3 if link.is_primary else 1,
        "dashes": not link.is_primary,
        "arrows": "to",
        "font": {"size": 10, "align": "middle"},
    }


async def build_port_topology(session: AsyncSession, datacenter_id: int) -> dict:
    devices_result = await session.execute(
        select(Device).where(Device.datacenter_id == datacenter_id).order_by(Device.name)
    )
    devices = list(devices_result.scalars().all())
    device_map = {d.id: d for d in devices}

    links_result = await session.execute(
        select(NetworkLink)
        .where(NetworkLink.datacenter_id == datacenter_id)
        .options(selectinload(NetworkLink.from_device), selectinload(NetworkLink.to_device))
    )
    links = list(links_result.scalars().all())

    branches_result = await session.execute(
        select(BranchSite)
        .where(BranchSite.datacenter_id == datacenter_id)
        .options(selectinload(BranchSite.primary_device), selectinload(BranchSite.backup_device))
    )
    branches = list(branches_result.scalars().all())

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()

    for device in devices:
        node = _device_node(device)
        nodes.append(node)
        seen_ids.add(node["id"])

    for branch in branches:
        branch_id = f"branch-{branch.id}"
        nodes.append({
            "id": branch_id,
            "label": f"📍 {branch.name}",
            "shape": "ellipse",
            "color": "#3b82f6",
            "title": branch.location or branch.name,
            "group": "branch",
        })
        seen_ids.add(branch_id)
        if branch.primary_device_id and branch.primary_device_id in device_map:
            edges.append({
                "id": f"branch-primary-{branch.id}",
                "from": f"dev-{branch.primary_device_id}",
                "to": branch_id,
                "label": f"{branch.primary_port or '—'}\n{LINK_LABELS.get(branch.primary_link_type, 'رابط')}",
                "color": {"color": LINK_COLORS.get(branch.primary_link_type, "#06b6d4")},
                "width": 2,
            })
        if branch.backup_enabled and branch.backup_device_id and branch.backup_device_id in device_map:
            backup_type = branch.backup_link_type or LinkType.WIRELESS
            edges.append({
                "id": f"branch-backup-{branch.id}",
                "from": f"dev-{branch.backup_device_id}",
                "to": branch_id,
                "label": f"{branch.backup_port or branch.backup_wireless_ssid or '—'}\nاحتياطي: {LINK_LABELS.get(backup_type, 'لاسلكي')}",
                "color": {"color": LINK_COLORS.get(backup_type, "#a855f7")},
                "width": 1,
                "dashes": True,
            })

    for link in links:
        if link.from_device_id in device_map and link.to_device_id in device_map:
            edges.append(_link_edge(link, device_map))

    if not edges:
        switches = [d for d in devices if d.device_type in (DeviceType.SWITCH, DeviceType.ROUTER, None)]
        for i, dev in enumerate(switches):
            if i + 1 < len(switches):
                edges.append({
                    "id": f"auto-{dev.id}-{switches[i + 1].id}",
                    "from": f"dev-{dev.id}",
                    "to": f"dev-{switches[i + 1].id}",
                    "label": "منطقي",
                    "dashes": True,
                    "color": {"color": "#475569"},
                })

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "device_count": len(devices),
            "link_count": len(links),
            "branch_count": len(branches),
            "link_types": {lt.value: LINK_LABELS[lt] for lt in LinkType},
        },
    }


async def get_device_port_summary(session: AsyncSession, device_id: int) -> dict:
    ports_result = await session.execute(
        select(SwitchPort).where(SwitchPort.device_id == device_id).order_by(SwitchPort.port_index, SwitchPort.name)
    )
    ports = list(ports_result.scalars().all())
    up = sum(1 for p in ports if p.oper_status.value == "up")
    return {
        "total": len(ports),
        "up": up,
        "down": len(ports) - up,
        "ports": ports,
    }
