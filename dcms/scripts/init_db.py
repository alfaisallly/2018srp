"""Initialize DCMS database with Iraqi datacenter sites and remove legacy demo data."""

import asyncio

from sqlalchemy import delete, select, text

from app.core.security import hash_password
from app.database import AsyncSessionLocal, engine
from app.models import (
    Base,
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
    User,
    VendorType,
)

LEGACY_DC_NAMES = ("DC-Riyadh-01",)

DC_MOROOR = {
    "name": "DC-MOROOR-01",
    "location": "بغداد، العراق — مديرية المرور العامة",
    "description": "مركز بيانات مديرية المرور العامة",
    "contact_email": "noc@moroor.gov.iq",
}

DC_MOI = {
    "name": "DC-MOI-01",
    "location": "بغداد، العراق — وزارة الداخلية",
    "description": "مركز بيانات وزارة الداخلية",
    "contact_email": "noc@moi.gov.iq",
}


async def migrate_schema(conn) -> None:
    migrations = [
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS server_id INTEGER",
        "ALTER TABLE alerts ADD COLUMN IF NOT EXISTS storage_id INTEGER",
        "ALTER TYPE protocoltype ADD VALUE IF NOT EXISTS 'ipmi'",
        "ALTER TYPE protocoltype ADD VALUE IF NOT EXISTS 'winrm'",
    ]
    for stmt in migrations:
        try:
            await conn.execute(text(stmt))
        except Exception:
            pass


async def cleanup_legacy_data(session) -> None:
    for legacy_name in LEGACY_DC_NAMES:
        result = await session.execute(select(DataCenter.id).where(DataCenter.name == legacy_name))
        row = result.first()
        if not row:
            continue
        dc_id = row[0]
        await session.execute(text("DELETE FROM alerts WHERE datacenter_id = :dc_id"), {"dc_id": dc_id})
        await session.execute(text("DELETE FROM network_maps WHERE datacenter_id = :dc_id"), {"dc_id": dc_id})
        await session.execute(
            text("DELETE FROM device_credentials WHERE device_id IN (SELECT id FROM devices WHERE datacenter_id = :dc_id)"),
            {"dc_id": dc_id},
        )
        await session.execute(text("DELETE FROM devices WHERE datacenter_id = :dc_id"), {"dc_id": dc_id})
        await session.execute(
            text("DELETE FROM server_credentials WHERE server_id IN (SELECT id FROM servers WHERE datacenter_id = :dc_id)"),
            {"dc_id": dc_id},
        )
        await session.execute(text("DELETE FROM servers WHERE datacenter_id = :dc_id"), {"dc_id": dc_id})
        await session.execute(
            text("DELETE FROM storage_credentials WHERE storage_id IN (SELECT id FROM storage_systems WHERE datacenter_id = :dc_id)"),
            {"dc_id": dc_id},
        )
        await session.execute(text("DELETE FROM storage_systems WHERE datacenter_id = :dc_id"), {"dc_id": dc_id})
        await session.execute(text("DELETE FROM datacenters WHERE id = :dc_id"), {"dc_id": dc_id})
        await session.flush()
        print(f"Removed legacy datacenter: {legacy_name}")


async def seed_datacenter(session, dc_info: dict, assets: dict) -> None:
    result = await session.execute(select(DataCenter).where(DataCenter.name == dc_info["name"]))
    if result.scalar_one_or_none():
        print(f"Datacenter already exists: {dc_info['name']}")
        return

    dc = DataCenter(**dc_info)
    session.add(dc)
    await session.flush()

    for name, ip, vendor, protocol, cred in assets.get("devices", []):
        device = Device(
            datacenter_id=dc.id,
            name=name,
            hostname=name.lower().replace("_", "-"),
            ip_address=ip,
            vendor=vendor,
        )
        session.add(device)
        await session.flush()
        session.add(DeviceCredential(device_id=device.id, protocol=protocol, **cred))

    for srv_info in assets.get("servers", []):
        srv = Server(datacenter_id=dc.id, **srv_info["data"])
        session.add(srv)
        await session.flush()
        session.add(ServerCredential(server_id=srv.id, **srv_info["cred"]))

    for sto_info in assets.get("storage", []):
        sto = StorageSystem(datacenter_id=dc.id, **sto_info["data"])
        session.add(sto)
        await session.flush()
        session.add(StorageCredential(storage_id=sto.id, **sto_info["cred"]))

    topo = assets.get("topology")
    if topo:
        session.add(
            NetworkMap(
                datacenter_id=dc.id,
                name=topo["name"],
                description=topo.get("description"),
                topology=topo["graph"],
            )
        )

    print(f"Created datacenter: {dc_info['name']}")


MOROOR_ASSETS = {
    "devices": [
        ("MR-Core-SW-01", "172.16.10.1", VendorType.CISCO, ProtocolType.SNMP, {"community": "public"}),
        ("MR-Edge-RTR-01", "172.16.10.2", VendorType.JUNIPER, ProtocolType.SSH, {"username": "admin", "password": "pass"}),
        ("MR-FW-01", "172.16.10.3", VendorType.FORTINET, ProtocolType.REST, {"api_token": "sample-token"}),
    ],
    "servers": [
        {
            "data": {
                "name": "MR-APP-SRV-01",
                "hostname": "mr-app-srv-01",
                "ip_address": "172.16.10.10",
                "os_type": ServerOSType.LINUX,
                "server_role": ServerRole.APPLICATION,
                "cpu_cores": 16,
                "ram_gb": 64,
            },
            "cred": {"protocol": ProtocolType.SSH, "username": "admin", "password": "pass", "port": 22},
        },
        {
            "data": {
                "name": "MR-DB-SRV-01",
                "hostname": "mr-db-srv-01",
                "ip_address": "172.16.10.11",
                "os_type": ServerOSType.LINUX,
                "server_role": ServerRole.DATABASE,
                "cpu_cores": 32,
                "ram_gb": 128,
            },
            "cred": {"protocol": ProtocolType.SSH, "username": "admin", "password": "pass", "port": 22},
        },
    ],
    "storage": [
        {
            "data": {
                "name": "MR-NAS-01",
                "hostname": "mr-nas-01",
                "ip_address": "172.16.10.20",
                "vendor": StorageVendor.NETAPP,
                "storage_type": StorageType.NAS,
                "total_capacity_tb": 80.0,
            },
            "cred": {"protocol": ProtocolType.SNMP, "community": "public", "port": 161},
        },
    ],
    "topology": {
        "name": "Topology-Moroor",
        "description": "خريطة شبكة مديرية المرور العامة",
        "graph": {
            "nodes": [
                {"id": "dc-moroor", "label": "مديرية المرور العامة", "shape": "box", "color": "#3b82f6"},
                {"id": "mr-sw", "label": "MR-Core-SW-01", "color": "#049fd9"},
                {"id": "mr-rtr", "label": "MR-Edge-RTR-01", "color": "#84bd00"},
                {"id": "mr-fw", "label": "MR-FW-01", "color": "#ee3124"},
                {"id": "mr-app", "label": "MR-APP-SRV-01", "color": "#8b5cf6"},
                {"id": "mr-db", "label": "MR-DB-SRV-01", "color": "#8b5cf6"},
                {"id": "mr-nas", "label": "MR-NAS-01", "color": "#f59e0b"},
            ],
            "edges": [
                {"from": "dc-moroor", "to": "mr-sw"},
                {"from": "mr-sw", "to": "mr-rtr"},
                {"from": "mr-rtr", "to": "mr-fw"},
                {"from": "mr-sw", "to": "mr-app"},
                {"from": "mr-sw", "to": "mr-db"},
                {"from": "mr-sw", "to": "mr-nas"},
            ],
        },
    },
}

MOI_ASSETS = {
    "devices": [
        ("MOI-Core-SW-01", "172.16.20.1", VendorType.CISCO, ProtocolType.SNMP, {"community": "public"}),
        ("MOI-RTR-01", "172.16.20.2", VendorType.JUNIPER, ProtocolType.SSH, {"username": "admin", "password": "pass"}),
        ("MOI-FW-01", "172.16.20.3", VendorType.FORTINET, ProtocolType.REST, {"api_token": "sample-token"}),
    ],
    "servers": [
        {
            "data": {
                "name": "MOI-WEB-SRV-01",
                "hostname": "moi-web-srv-01",
                "ip_address": "172.16.20.10",
                "os_type": ServerOSType.WINDOWS,
                "server_role": ServerRole.WEB,
                "cpu_cores": 8,
                "ram_gb": 32,
            },
            "cred": {"protocol": ProtocolType.SSH, "username": "administrator", "password": "pass", "port": 22},
        },
        {
            "data": {
                "name": "MOI-HV-SRV-01",
                "hostname": "moi-hv-srv-01",
                "ip_address": "172.16.20.11",
                "os_type": ServerOSType.VMWARE,
                "server_role": ServerRole.HYPERVISOR,
                "cpu_cores": 48,
                "ram_gb": 256,
            },
            "cred": {"protocol": ProtocolType.REST, "api_token": "sample-token", "username": "admin", "password": "pass", "port": 443},
        },
    ],
    "storage": [
        {
            "data": {
                "name": "MOI-SAN-01",
                "hostname": "moi-san-01",
                "ip_address": "172.16.20.20",
                "vendor": StorageVendor.DELL_EMC,
                "storage_type": StorageType.SAN,
                "total_capacity_tb": 200.0,
            },
            "cred": {"protocol": ProtocolType.SNMP, "community": "public", "port": 161},
        },
        {
            "data": {
                "name": "MOI-NAS-02",
                "hostname": "moi-nas-02",
                "ip_address": "172.16.20.21",
                "vendor": StorageVendor.QNAP,
                "storage_type": StorageType.NAS,
                "total_capacity_tb": 60.0,
            },
            "cred": {"protocol": ProtocolType.REST, "api_token": "sample-token", "port": 443},
        },
    ],
    "topology": {
        "name": "Topology-MOI",
        "description": "خريطة شبكة وزارة الداخلية",
        "graph": {
            "nodes": [
                {"id": "dc-moi", "label": "وزارة الداخلية", "shape": "box", "color": "#3b82f6"},
                {"id": "moi-sw", "label": "MOI-Core-SW-01", "color": "#049fd9"},
                {"id": "moi-rtr", "label": "MOI-RTR-01", "color": "#84bd00"},
                {"id": "moi-fw", "label": "MOI-FW-01", "color": "#ee3124"},
                {"id": "moi-web", "label": "MOI-WEB-SRV-01", "color": "#8b5cf6"},
                {"id": "moi-hv", "label": "MOI-HV-SRV-01", "color": "#8b5cf6"},
                {"id": "moi-san", "label": "MOI-SAN-01", "color": "#f59e0b"},
                {"id": "moi-nas", "label": "MOI-NAS-02", "color": "#f59e0b"},
            ],
            "edges": [
                {"from": "dc-moi", "to": "moi-sw"},
                {"from": "moi-sw", "to": "moi-rtr"},
                {"from": "moi-rtr", "to": "moi-fw"},
                {"from": "moi-sw", "to": "moi-web"},
                {"from": "moi-sw", "to": "moi-hv"},
                {"from": "moi-sw", "to": "moi-san"},
                {"from": "moi-sw", "to": "moi-nas"},
            ],
        },
    },
}


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await migrate_schema(conn)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            session.add(
                User(
                    username="admin",
                    email="admin@dcms.local",
                    hashed_password=hash_password("admin123"),
                    full_name="مدير النظام",
                    role="admin",
                )
            )
            print("Created admin user: admin / admin123")

        await cleanup_legacy_data(session)
        await seed_datacenter(session, DC_MOROOR, MOROOR_ASSETS)
        await seed_datacenter(session, DC_MOI, MOI_ASSETS)

        await session.commit()
    print("Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(init_db())
