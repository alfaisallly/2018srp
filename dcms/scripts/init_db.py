"""Initialize DCMS database with default admin user and sample data."""

import asyncio

from sqlalchemy import select

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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

        result = await session.execute(select(DataCenter).where(DataCenter.name == "DC-Riyadh-01"))
        if not result.scalar_one_or_none():
            dc = DataCenter(
                name="DC-Riyadh-01",
                location="الرياض، المملكة العربية السعودية",
                description="مركز البيانات الرئيسي",
                contact_email="noc@example.com",
            )
            session.add(dc)
            await session.flush()

            devices = [
                ("Core-SW-01", "10.0.1.1", VendorType.CISCO, ProtocolType.SNMP, {"community": "public"}),
                ("Edge-RTR-01", "10.0.1.2", VendorType.JUNIPER, ProtocolType.SSH, {"username": "admin", "password": "pass"}),
                ("FW-01", "10.0.1.3", VendorType.FORTINET, ProtocolType.REST, {"api_token": "sample-token"}),
            ]
            for name, ip, vendor, protocol, cred in devices:
                device = Device(
                    datacenter_id=dc.id,
                    name=name,
                    hostname=name.lower(),
                    ip_address=ip,
                    vendor=vendor,
                )
                session.add(device)
                await session.flush()
                session.add(
                    DeviceCredential(
                        device_id=device.id,
                        protocol=protocol,
                        **cred,
                    )
                )

            session.add(
                NetworkMap(
                    datacenter_id=dc.id,
                    name="Topology-Riyadh",
                    description="خريطة الشبكة الرئيسية",
                    topology={
                        "nodes": [
                            {"id": "dc-1", "label": "DC-Riyadh-01", "shape": "box", "color": "#3b82f6"},
                            {"id": "dev-1", "label": "Core-SW-01", "color": "#049fd9"},
                            {"id": "dev-2", "label": "Edge-RTR-01", "color": "#84bd00"},
                            {"id": "dev-3", "label": "FW-01", "color": "#ee3124"},
                        ],
                        "edges": [
                            {"from": "dc-1", "to": "dev-1"},
                            {"from": "dev-1", "to": "dev-2"},
                            {"from": "dev-2", "to": "dev-3"},
                        ],
                    },
                )
            )
            print("Created sample data center with 3 devices")

            srv = Server(
                datacenter_id=dc.id,
                name="APP-SRV-01",
                hostname="app-srv-01",
                ip_address="10.0.2.10",
                os_type=ServerOSType.LINUX,
                server_role=ServerRole.APPLICATION,
                cpu_cores=8,
                ram_gb=32,
            )
            session.add(srv)
            await session.flush()
            session.add(ServerCredential(server_id=srv.id, protocol=ProtocolType.SSH, username="root", password="pass", port=22))

            sto = StorageSystem(
                datacenter_id=dc.id,
                name="NAS-Primary",
                hostname="nas-primary",
                ip_address="10.0.2.20",
                vendor=StorageVendor.NETAPP,
                storage_type=StorageType.NAS,
                total_capacity_tb=50.0,
            )
            session.add(sto)
            await session.flush()
            session.add(StorageCredential(storage_id=sto.id, protocol=ProtocolType.SNMP, community="public", port=161))
            print("Created sample server and storage")

        await session.commit()
    print("Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(init_db())
