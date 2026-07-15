"""Apply parsed Excel data to the database."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DataCenter,
    Device,
    DeviceCredential,
    NetworkMap,
    ProtocolType,
    Server,
    ServerCredential,
    ServerOSType,
    ServerRole,
    StorageCredential,
    StorageSystem,
    StorageType,
    StorageVendor,
    VendorType,
)
from app.services.datacenter_overview import infer_device_type
from app.services.excel_import import ParsedAsset, ParsedLink, build_topology


async def _get_or_create_dc(session: AsyncSession, name: str) -> DataCenter:
    result = await session.execute(select(DataCenter).where(DataCenter.name == name))
    dc = result.scalar_one_or_none()
    if dc:
        return dc
    dc = DataCenter(name=name, location="مستورد من Excel", description=f"مركز بيانات {name}")
    session.add(dc)
    await session.flush()
    return dc


def _map_vendor(v: str | None) -> VendorType:
    mapping = {
        "cisco": VendorType.CISCO,
        "juniper": VendorType.JUNIPER,
        "fortinet": VendorType.FORTINET,
    }
    return mapping.get(v or "", VendorType.GENERIC)


def _map_storage_vendor(v: str | None) -> StorageVendor:
    try:
        return StorageVendor(v or "generic")
    except ValueError:
        return StorageVendor.GENERIC


def _map_protocol(p: str | None) -> ProtocolType:
    try:
        return ProtocolType((p or "snmp").lower())
    except ValueError:
        return ProtocolType.SNMP


async def _find_existing_asset(session: AsyncSession, ip: str):
    for model, prefix in ((Device, "dev"), (Server, "srv"), (StorageSystem, "sto")):
        result = await session.execute(select(model).where(model.ip_address == ip))
        row = result.scalar_one_or_none()
        if row:
            return prefix, row
    return None, None


async def apply_excel_import(
    session: AsyncSession,
    assets: list[ParsedAsset],
    links: list[ParsedLink],
    skip_existing: bool = True,
) -> dict:
    stats = {"imported": 0, "skipped": 0, "datacenters": 0, "maps_updated": 0, "errors": []}
    dc_cache: dict[str, DataCenter] = {}
    asset_node_ids: dict[str, dict[str, str]] = {}

    for asset in assets:
        try:
            if asset.datacenter not in dc_cache:
                dc_cache[asset.datacenter] = await _get_or_create_dc(session, asset.datacenter)
            dc = dc_cache[asset.datacenter]

            prefix, existing = await _find_existing_asset(session, asset.ip_address)
            if existing:
                if skip_existing:
                    stats["skipped"] += 1
                    node_id = f"{prefix}-{existing.id}"
                    if asset.datacenter not in asset_node_ids:
                        asset_node_ids[asset.datacenter] = {}
                    asset_node_ids[asset.datacenter][asset.name] = node_id
                    asset_node_ids[asset.datacenter][asset.ip_address] = node_id
                    continue

            if asset.asset_type == "device":
                vendor = _map_vendor(asset.vendor)
                dev = Device(
                    datacenter_id=dc.id,
                    name=asset.name,
                    hostname=asset.hostname,
                    ip_address=asset.ip_address,
                    vendor=vendor,
                    device_type=infer_device_type(vendor, asset.name, asset.model),
                    model=asset.model,
                )
                session.add(dev)
                await session.flush()
                cred = DeviceCredential(
                    device_id=dev.id,
                    protocol=_map_protocol(asset.protocol),
                    username=asset.username,
                    password=asset.password,
                    community=asset.community,
                    api_token=asset.api_token,
                    port=asset.port,
                )
                session.add(cred)
                node_id = f"dev-{dev.id}"

            elif asset.asset_type == "server":
                try:
                    os_type = ServerOSType(asset.os_type or "linux")
                except ValueError:
                    os_type = ServerOSType.OTHER
                try:
                    role = ServerRole(asset.server_role or "other")
                except ValueError:
                    role = ServerRole.OTHER
                srv = Server(
                    datacenter_id=dc.id,
                    name=asset.name,
                    hostname=asset.hostname,
                    ip_address=asset.ip_address,
                    os_type=os_type,
                    server_role=role,
                    notes=asset.notes,
                )
                session.add(srv)
                await session.flush()
                session.add(
                    ServerCredential(
                        server_id=srv.id,
                        protocol=_map_protocol(asset.protocol),
                        username=asset.username,
                        password=asset.password,
                        community=asset.community,
                        api_token=asset.api_token,
                        port=asset.port,
                    )
                )
                node_id = f"srv-{srv.id}"

            else:
                try:
                    stype = StorageType(asset.storage_type or "san")
                except ValueError:
                    stype = StorageType.OTHER
                sto = StorageSystem(
                    datacenter_id=dc.id,
                    name=asset.name,
                    hostname=asset.hostname,
                    ip_address=asset.ip_address,
                    vendor=_map_storage_vendor(asset.vendor),
                    model=asset.model,
                    storage_type=stype,
                    notes=asset.notes,
                )
                session.add(sto)
                await session.flush()
                session.add(
                    StorageCredential(
                        storage_id=sto.id,
                        protocol=_map_protocol(asset.protocol),
                        username=asset.username,
                        password=asset.password,
                        community=asset.community,
                        api_token=asset.api_token,
                        port=asset.port,
                    )
                )
                node_id = f"sto-{sto.id}"

            if asset.datacenter not in asset_node_ids:
                asset_node_ids[asset.datacenter] = {}
            asset_node_ids[asset.datacenter][asset.name] = node_id
            asset_node_ids[asset.datacenter][asset.ip_address] = node_id
            stats["imported"] += 1

        except Exception as exc:
            stats["errors"].append(f"صف {asset.row}: {exc}")

    stats["datacenters"] = len(dc_cache)

    for dc_name, dc in dc_cache.items():
        ids = asset_node_ids.get(dc_name, {})
        topology = build_topology(assets, links, dc_name, ids)
        result = await session.execute(
            select(NetworkMap).where(
                NetworkMap.datacenter_id == dc.id,
                NetworkMap.name == f"Excel-{dc_name}",
            )
        )
        existing_map = result.scalar_one_or_none()
        if existing_map:
            existing_map.topology = topology
        else:
            session.add(
                NetworkMap(
                    datacenter_id=dc.id,
                    name=f"Excel-{dc_name}",
                    description="مخطط مستورد من Excel",
                    topology=topology,
                )
            )
        stats["maps_updated"] += 1

    return stats
