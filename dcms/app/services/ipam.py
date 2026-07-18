"""IP Address Management — prefixes, allocations, asset sync."""

import ipaddress
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Device, IpAddress, IpAddressStatus, IpPrefix, Server, StorageSystem


def _iter_hosts(network: ipaddress.IPv4Network | ipaddress.IPv6Network):
    if network.num_addresses <= 2:
        yield from network
        return
    hosts = list(network.hosts())
    if hosts:
        yield from hosts
    else:
        yield from network


async def sync_prefix_addresses(session: AsyncSession, prefix_id: int) -> dict:
    result = await session.execute(select(IpPrefix).where(IpPrefix.id == prefix_id))
    prefix = result.scalar_one_or_none()
    if not prefix:
        raise ValueError("Prefix not found")

    network = ipaddress.ip_network(prefix.cidr, strict=False)
    existing = await session.execute(select(IpAddress).where(IpAddress.prefix_id == prefix_id))
    addr_map = {a.address: a for a in existing.scalars().all()}

    assigned_ips: dict[str, dict] = {}
    for device in (await session.execute(select(Device).where(Device.datacenter_id == prefix.datacenter_id))).scalars():
        assigned_ips[device.ip_address] = {"asset_type": "device", "asset_id": device.id, "hostname": device.name, "device_id": device.id}
    for server in (await session.execute(select(Server).where(Server.datacenter_id == prefix.datacenter_id))).scalars():
        assigned_ips[server.ip_address] = {"asset_type": "server", "asset_id": server.id, "hostname": server.name, "device_id": None}
    for sto in (await session.execute(select(StorageSystem).where(StorageSystem.datacenter_id == prefix.datacenter_id))).scalars():
        assigned_ips[sto.ip_address] = {"asset_type": "storage", "asset_id": sto.id, "hostname": sto.name, "device_id": None}

    created = updated = 0
    for host in _iter_hosts(network):
        ip_str = str(host)
        if ip_str not in network:
            continue
        meta = assigned_ips.get(ip_str)
        status = IpAddressStatus.ASSIGNED if meta else IpAddressStatus.FREE
        if ip_str in addr_map:
            row = addr_map[ip_str]
            if meta:
                row.status = IpAddressStatus.ASSIGNED
                row.hostname = meta["hostname"]
                row.asset_type = meta["asset_type"]
                row.asset_id = meta["asset_id"]
                row.device_id = meta["device_id"]
                updated += 1
            elif row.status == IpAddressStatus.ASSIGNED and not row.asset_id:
                row.status = IpAddressStatus.FREE
                row.hostname = None
                updated += 1
        else:
            session.add(
                IpAddress(
                    prefix_id=prefix_id,
                    address=ip_str,
                    status=status,
                    hostname=meta["hostname"] if meta else None,
                    asset_type=meta["asset_type"] if meta else None,
                    asset_id=meta["asset_id"] if meta else None,
                    device_id=meta["device_id"] if meta else None,
                )
            )
            created += 1

    return {"created": created, "updated": updated, "total_hosts": network.num_addresses}


async def prefix_utilization(session: AsyncSession, prefix_id: int) -> dict:
    result = await session.execute(select(IpAddress).where(IpAddress.prefix_id == prefix_id))
    rows = list(result.scalars().all())
    total = len(rows)
    assigned = sum(1 for r in rows if r.status == IpAddressStatus.ASSIGNED)
    reserved = sum(1 for r in rows if r.status == IpAddressStatus.RESERVED)
    free = sum(1 for r in rows if r.status == IpAddressStatus.FREE)
    return {
        "total": total,
        "assigned": assigned,
        "reserved": reserved,
        "free": free,
        "utilization_pct": round((assigned + reserved) / total * 100, 1) if total else 0,
    }


async def find_ip_conflicts(session: AsyncSession, datacenter_id: int | None = None) -> list[dict]:
    """Detect duplicate IPs across asset types within a datacenter."""
    conflicts: list[dict] = []
    dc_filter = []
    if datacenter_id:
        dc_filter = [datacenter_id]

    async def ips_for(model, asset_type: str):
        q = select(model)
        if datacenter_id:
            q = q.where(model.datacenter_id == datacenter_id)
        return [(a.id, a.name, a.ip_address, a.datacenter_id, asset_type) for a in (await session.execute(q)).scalars()]

    all_rows = []
    for model, atype in [(Device, "device"), (Server, "server"), (StorageSystem, "storage")]:
        all_rows.extend(await ips_for(model, atype))

    by_ip: dict[str, list] = {}
    for row in all_rows:
        by_ip.setdefault(row[2], []).append(row)

    for ip, entries in by_ip.items():
        if len(entries) > 1:
            conflicts.append({
                "ip_address": ip,
                "assets": [{"id": e[0], "name": e[1], "type": e[4], "datacenter_id": e[3]} for e in entries],
            })
    return conflicts
