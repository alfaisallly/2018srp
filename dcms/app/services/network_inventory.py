"""Network inventory: ports, VLANs, firewall rules, and branch site seed data."""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BranchSite,
    DataCenter,
    Device,
    DeviceType,
    DeviceVlan,
    FirewallAction,
    FirewallRule,
    LinkType,
    NetworkLink,
    PortOperStatus,
    SwitchPort,
    VendorType,
)

MOROOR_NETWORK = {
    "vlans": [
        {"vlan_id": 10, "name": "Management", "subnet": "172.16.10.0/24", "gateway": "172.16.10.1", "device": "MR-Core-SW-01"},
        {"vlan_id": 20, "name": "Servers", "subnet": "172.16.10.0/24", "gateway": "172.16.10.1", "device": "MR-Core-SW-01"},
        {"vlan_id": 30, "name": "Storage", "subnet": "172.16.10.0/24", "gateway": "172.16.10.1", "device": "MR-Core-SW-01"},
        {"vlan_id": 100, "name": "Branch-Transit", "subnet": "10.100.0.0/24", "gateway": "10.100.0.1", "device": "MR-Edge-RTR-01"},
    ],
    "ports": {
        "MR-Core-SW-01": [
            {"name": "Gi1/0/1", "index": 1, "status": "up", "speed": 10000, "mode": "trunk", "trunk_vlans": [10, 20, 30], "link": "fiber", "connected": ("MR-Edge-RTR-01", "ge-0/0/0"), "desc": "Uplink to Edge Router"},
            {"name": "Gi1/0/2", "index": 2, "status": "up", "speed": 1000, "mode": "access", "vlan": 20, "connected": ("MR-APP-SRV-01", "eth0"), "services": ["HTTP", "HTTPS"], "desc": "App Server"},
            {"name": "Gi1/0/3", "index": 3, "status": "up", "speed": 1000, "mode": "access", "vlan": 20, "connected": ("MR-DB-SRV-01", "eth0"), "services": ["MySQL"], "desc": "DB Server"},
            {"name": "Gi1/0/4", "index": 4, "status": "up", "speed": 10000, "mode": "access", "vlan": 30, "link": "fiber", "connected": ("MR-Pure-R40-01", "ct0"), "services": ["iSCSI", "NFS"], "desc": "Pure Storage SAN"},
            {"name": "Gi1/0/5", "index": 5, "status": "up", "speed": 1000, "mode": "access", "vlan": 10, "desc": "Management"},
            {"name": "Gi1/0/6", "index": 6, "status": "down", "speed": 1000, "mode": "access", "vlan": 10, "desc": "Spare"},
        ],
        "MR-Edge-RTR-01": [
            {"name": "ge-0/0/0", "index": 0, "status": "up", "speed": 10000, "mode": "trunk", "trunk_vlans": [10, 20, 30, 100], "link": "fiber", "connected": ("MR-Core-SW-01", "Gi1/0/1"), "desc": "Core Switch Uplink"},
            {"name": "ge-0/0/1", "index": 1, "status": "up", "speed": 1000, "mode": "access", "vlan": 100, "link": "fiber", "connected": ("MR-FW-01", "port1"), "desc": "To Firewall WAN"},
            {"name": "ge-0/0/2", "index": 2, "status": "up", "speed": 1000, "mode": "access", "vlan": 100, "link": "wireless", "desc": "WWAN Backup LTE"},
        ],
    },
    "links": [
        {"from": "MR-Core-SW-01", "from_port": "Gi1/0/1", "to": "MR-Edge-RTR-01", "to_port": "ge-0/0/0", "type": "fiber", "bw": 10000, "primary": True},
        {"from": "MR-Edge-RTR-01", "from_port": "ge-0/0/1", "to": "MR-FW-01", "to_port": "port1", "type": "fiber", "bw": 1000, "primary": True},
    ],
    "firewall_rules": {
        "MR-FW-01": [
            {"name": "Allow-Management", "action": "allow", "src": "172.16.10.0/24", "dst": "any", "service": "SSH,HTTPS", "zone_in": "trust", "zone_out": "trust"},
            {"name": "Allow-Web", "action": "allow", "src": "any", "dst": "172.16.10.10", "service": "HTTP,HTTPS", "zone_in": "untrust", "zone_out": "trust"},
            {"name": "Deny-All", "action": "deny", "src": "any", "dst": "any", "service": "any", "zone_in": "untrust", "zone_out": "trust"},
        ],
    },
    "branches": [
        {
            "name": "فرع الكرخ",
            "location": "بغداد — الكرخ",
            "primary_device": "MR-Edge-RTR-01",
            "primary_port": "ge-0/0/3",
            "primary_link": "fiber",
            "backup": True,
            "backup_link": "wireless",
            "backup_device": "MR-Edge-RTR-01",
            "backup_port": "ge-0/0/2",
            "backup_ssid": "MR-BRANCH-LTE",
        },
        {
            "name": "فرع الرصافة",
            "location": "بغداد — الرصافة",
            "primary_device": "MR-Core-SW-01",
            "primary_port": "Gi1/0/7",
            "primary_link": "fiber",
            "backup": True,
            "backup_link": "wireless",
            "backup_device": "MR-Edge-RTR-01",
            "backup_port": "ge-0/0/2",
            "backup_ssid": "MR-RUSafa-LTE",
        },
    ],
}

MOI_NETWORK = {
    "vlans": [
        {"vlan_id": 10, "name": "Management", "subnet": "172.16.20.0/24", "gateway": "172.16.20.1", "device": "MOI-Core-SW-01"},
        {"vlan_id": 50, "name": "Web-Services", "subnet": "172.16.20.0/24", "gateway": "172.16.20.1", "device": "MOI-Core-SW-01"},
        {"vlan_id": 60, "name": "Virtualization", "subnet": "172.16.20.0/24", "gateway": "172.16.20.1", "device": "MOI-Core-SW-01"},
        {"vlan_id": 200, "name": "WAN-Transit", "subnet": "10.200.0.0/24", "gateway": "10.200.0.1", "device": "MOI-RTR-01"},
    ],
    "ports": {
        "MOI-Core-SW-01": [
            {"name": "Gi1/0/1", "index": 1, "status": "up", "speed": 10000, "mode": "trunk", "trunk_vlans": [10, 50, 60], "link": "fiber", "connected": ("MOI-RTR-01", "ge-0/0/0"), "desc": "Core Router Uplink"},
            {"name": "Gi1/0/2", "index": 2, "status": "up", "speed": 1000, "mode": "access", "vlan": 50, "connected": ("MOI-WEB-SRV-01", "eth0"), "services": ["HTTP", "HTTPS", "RDP"], "desc": "Web Server"},
            {"name": "Gi1/0/3", "index": 3, "status": "up", "speed": 10000, "mode": "access", "vlan": 60, "link": "fiber", "connected": ("MOI-HV-SRV-01", "vmnic0"), "services": ["vMotion", "Management"], "desc": "Hypervisor"},
            {"name": "Gi1/0/4", "index": 4, "status": "up", "speed": 10000, "mode": "access", "vlan": 60, "link": "fiber", "connected": ("MOI-Pure-R40-01", "ct0"), "services": ["iSCSI"], "desc": "Storage SAN"},
        ],
        "MOI-RTR-01": [
            {"name": "ge-0/0/0", "index": 0, "status": "up", "speed": 10000, "mode": "trunk", "trunk_vlans": [10, 50, 60, 200], "link": "fiber", "connected": ("MOI-Core-SW-01", "Gi1/0/1"), "desc": "Core Switch"},
            {"name": "ge-0/0/1", "index": 1, "status": "up", "speed": 1000, "mode": "access", "vlan": 200, "link": "fiber", "connected": ("MOI-FW-01", "port1"), "desc": "Firewall WAN"},
            {"name": "ge-0/0/2", "index": 2, "status": "up", "speed": 1000, "mode": "access", "vlan": 200, "link": "wireless", "desc": "LTE Backup"},
        ],
    },
    "links": [
        {"from": "MOI-Core-SW-01", "from_port": "Gi1/0/1", "to": "MOI-RTR-01", "to_port": "ge-0/0/0", "type": "fiber", "bw": 10000, "primary": True},
        {"from": "MOI-RTR-01", "from_port": "ge-0/0/1", "to": "MOI-FW-01", "to_port": "port1", "type": "fiber", "bw": 1000, "primary": True},
    ],
    "firewall_rules": {
        "MOI-FW-01": [
            {"name": "Allow-NOC", "action": "allow", "src": "172.16.20.0/24", "dst": "any", "service": "SSH,SNMP,HTTPS", "zone_in": "trust", "zone_out": "trust"},
            {"name": "Allow-Public-Web", "action": "allow", "src": "any", "dst": "172.16.20.10", "service": "HTTPS", "zone_in": "untrust", "zone_out": "trust"},
            {"name": "Block-ICMP-External", "action": "deny", "src": "any", "dst": "172.16.20.0/24", "service": "ICMP", "zone_in": "untrust", "zone_out": "trust"},
        ],
    },
    "branches": [
        {
            "name": "فرع البصرة",
            "location": "محافظة البصرة",
            "primary_device": "MOI-RTR-01",
            "primary_port": "ge-0/0/3",
            "primary_link": "fiber",
            "backup": True,
            "backup_link": "wireless",
            "backup_device": "MOI-RTR-01",
            "backup_port": "ge-0/0/2",
            "backup_ssid": "MOI-Basra-LTE",
        },
    ],
}

NETWORK_BY_DC = {
    "DC-MOROOR-01": MOROOR_NETWORK,
    "DC-MOI-01": MOI_NETWORK,
}


async def _device_by_name(session: AsyncSession, dc_id: int, name: str) -> Device | None:
    result = await session.execute(
        select(Device).where(Device.datacenter_id == dc_id, Device.name == name)
    )
    return result.scalar_one_or_none()


async def seed_network_inventory(session: AsyncSession, dc_name: str) -> dict:
    net_data = NETWORK_BY_DC.get(dc_name)
    if not net_data:
        return {"skipped": True}

    dc_result = await session.execute(select(DataCenter).where(DataCenter.name == dc_name))
    dc = dc_result.scalar_one_or_none()
    if not dc:
        return {"skipped": True}

    existing = await session.execute(
        select(func.count()).select_from(SwitchPort).join(Device).where(Device.datacenter_id == dc.id)
    )
    if existing.scalar_one() > 0:
        return {"skipped": True, "reason": "already_seeded"}

    device_cache: dict[str, Device] = {}
    dev_result = await session.execute(select(Device).where(Device.datacenter_id == dc.id))
    for d in dev_result.scalars().all():
        device_cache[d.name] = d

    stats = {"ports": 0, "vlans": 0, "links": 0, "firewall_rules": 0, "branches": 0}

    for vlan in net_data["vlans"]:
        dev = device_cache.get(vlan["device"])
        session.add(
            DeviceVlan(
                datacenter_id=dc.id,
                device_id=dev.id if dev else None,
                vlan_id=vlan["vlan_id"],
                name=vlan["name"],
                subnet=vlan.get("subnet"),
                gateway=vlan.get("gateway"),
                status="active",
            )
        )
        stats["vlans"] += 1

    for dev_name, ports in net_data["ports"].items():
        device = device_cache.get(dev_name)
        if not device:
            continue
        for p in ports:
            connected_id = None
            connected_port = None
            if p.get("connected"):
                conn_name, conn_port = p["connected"]
                conn_dev = device_cache.get(conn_name)
                if conn_dev:
                    connected_id = conn_dev.id
                    connected_port = conn_port
            link_type = LinkType(p["link"]) if p.get("link") else None
            session.add(
                SwitchPort(
                    device_id=device.id,
                    name=p["name"],
                    port_index=p.get("index"),
                    description=p.get("desc"),
                    oper_status=PortOperStatus(p["status"]),
                    speed_mbps=p.get("speed"),
                    vlan_mode=p.get("mode", "access"),
                    access_vlan=p.get("vlan"),
                    trunk_vlans=p.get("trunk_vlans"),
                    connected_device_id=connected_id,
                    connected_port_name=connected_port,
                    link_type=link_type,
                    services=p.get("services"),
                    last_sync_at=datetime.now(timezone.utc),
                )
            )
            stats["ports"] += 1

    await session.flush()

    for link in net_data["links"]:
        from_dev = device_cache.get(link["from"])
        to_dev = device_cache.get(link["to"])
        if from_dev and to_dev:
            session.add(
                NetworkLink(
                    datacenter_id=dc.id,
                    from_device_id=from_dev.id,
                    from_port=link["from_port"],
                    to_device_id=to_dev.id,
                    to_port=link["to_port"],
                    link_type=LinkType(link["type"]),
                    is_primary=link.get("primary", True),
                    bandwidth_mbps=link.get("bw"),
                    status="up",
                )
            )
            stats["links"] += 1

    for fw_name, rules in net_data.get("firewall_rules", {}).items():
        fw_dev = device_cache.get(fw_name)
        if not fw_dev:
            continue
        for i, rule in enumerate(rules):
            session.add(
                FirewallRule(
                    device_id=fw_dev.id,
                    rule_id=str(i + 1),
                    name=rule["name"],
                    action=FirewallAction(rule["action"]),
                    source=rule.get("src"),
                    destination=rule.get("dst"),
                    service=rule.get("service"),
                    zone_in=rule.get("zone_in"),
                    zone_out=rule.get("zone_out"),
                    order_index=i,
                    enabled=True,
                )
            )
            stats["firewall_rules"] += 1

    for branch in net_data.get("branches", []):
        primary = device_cache.get(branch["primary_device"])
        backup = device_cache.get(branch.get("backup_device", ""))
        session.add(
            BranchSite(
                datacenter_id=dc.id,
                name=branch["name"],
                location=branch.get("location"),
                primary_device_id=primary.id if primary else None,
                primary_port=branch.get("primary_port"),
                primary_link_type=LinkType(branch.get("primary_link", "fiber")),
                backup_enabled=branch.get("backup", False),
                backup_link_type=LinkType(branch["backup_link"]) if branch.get("backup_link") else None,
                backup_device_id=backup.id if backup else None,
                backup_port=branch.get("backup_port"),
                backup_wireless_ssid=branch.get("backup_ssid"),
                status="active",
            )
        )
        stats["branches"] += 1

    return stats


async def get_network_overview(session: AsyncSession, datacenter_id: int | None = None) -> dict:
    port_q = select(func.count()).select_from(SwitchPort)
    vlan_q = select(func.count()).select_from(DeviceVlan)
    link_q = select(func.count()).select_from(NetworkLink)
    fw_q = select(func.count()).select_from(FirewallRule)
    branch_q = select(func.count()).select_from(BranchSite)

    if datacenter_id:
        port_q = port_q.join(Device).where(Device.datacenter_id == datacenter_id)
        vlan_q = vlan_q.where(DeviceVlan.datacenter_id == datacenter_id)
        link_q = link_q.where(NetworkLink.datacenter_id == datacenter_id)
        fw_q = fw_q.join(Device).where(Device.datacenter_id == datacenter_id)
        branch_q = branch_q.where(BranchSite.datacenter_id == datacenter_id)

    ports_total = (await session.execute(port_q)).scalar_one()
    ports_up = (
        await session.execute(
            port_q.where(SwitchPort.oper_status == PortOperStatus.UP)
            if not datacenter_id
            else select(func.count()).select_from(SwitchPort).join(Device).where(
                Device.datacenter_id == datacenter_id, SwitchPort.oper_status == PortOperStatus.UP
            )
        )
    ).scalar_one()

    return {
        "ports_total": ports_total,
        "ports_up": ports_up,
        "ports_down": ports_total - ports_up,
        "vlans_total": (await session.execute(vlan_q)).scalar_one(),
        "links_total": (await session.execute(link_q)).scalar_one(),
        "firewall_rules_total": (await session.execute(fw_q)).scalar_one(),
        "branch_sites_total": (await session.execute(branch_q)).scalar_one(),
    }


async def clear_network_inventory(session: AsyncSession, datacenter_id: int) -> None:
    device_ids = select(Device.id).where(Device.datacenter_id == datacenter_id)
    await session.execute(delete(SwitchPort).where(SwitchPort.device_id.in_(device_ids)))
    await session.execute(delete(DeviceVlan).where(DeviceVlan.datacenter_id == datacenter_id))
    await session.execute(delete(NetworkLink).where(NetworkLink.datacenter_id == datacenter_id))
    await session.execute(delete(BranchSite).where(BranchSite.datacenter_id == datacenter_id))
    await session.execute(delete(FirewallRule).where(FirewallRule.device_id.in_(device_ids)))
