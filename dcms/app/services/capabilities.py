"""Platform capability registry and live status."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DataCenter,
    Device,
    DeviceConfigBackup,
    IntegrationEndpoint,
    IntegrationType,
    IpPrefix,
    Sensor,
    VendorType,
)


CAPABILITIES = [
    {
        "id": "datacenters",
        "icon": "🏢",
        "title_key": "capabilities.datacenters",
        "description_key": "capabilities.datacenters_desc",
    },
    {
        "id": "cisco_juniper",
        "icon": "🔀",
        "title_key": "capabilities.cisco_juniper",
        "description_key": "capabilities.cisco_juniper_desc",
    },
    {
        "id": "ipam",
        "icon": "🌐",
        "title_key": "capabilities.ipam",
        "description_key": "capabilities.ipam_desc",
    },
    {
        "id": "snmp",
        "icon": "📡",
        "title_key": "capabilities.snmp",
        "description_key": "capabilities.snmp_desc",
    },
    {
        "id": "config_backup",
        "icon": "💾",
        "title_key": "capabilities.config_backup",
        "description_key": "capabilities.config_backup_desc",
    },
    {
        "id": "web_dashboard",
        "icon": "📊",
        "title_key": "capabilities.web_dashboard",
        "description_key": "capabilities.web_dashboard_desc",
    },
    {
        "id": "prtg",
        "icon": "🔗",
        "title_key": "capabilities.prtg",
        "description_key": "capabilities.prtg_desc",
    },
    {
        "id": "vmware",
        "icon": "☁️",
        "title_key": "capabilities.vmware",
        "description_key": "capabilities.vmware_desc",
    },
]


async def get_platform_capabilities(session: AsyncSession) -> dict:
    dc_count = (await session.execute(select(func.count(DataCenter.id)))).scalar() or 0
    device_count = (await session.execute(select(func.count(Device.id)))).scalar() or 0
    cisco_juniper = (
        await session.execute(
            select(func.count(Device.id)).where(Device.vendor.in_([VendorType.CISCO, VendorType.JUNIPER]))
        )
    ).scalar() or 0
    prefix_count = (await session.execute(select(func.count(IpPrefix.id)))).scalar() or 0
    backup_count = (await session.execute(select(func.count(DeviceConfigBackup.id)))).scalar() or 0
    sensor_count = (await session.execute(select(func.count(Sensor.id)))).scalar() or 0
    prtg_count = (
        await session.execute(
            select(func.count(IntegrationEndpoint.id)).where(
                IntegrationEndpoint.integration_type == IntegrationType.PRTG,
                IntegrationEndpoint.enabled.is_(True),
            )
        )
    ).scalar() or 0
    vmware_count = (
        await session.execute(
            select(func.count(IntegrationEndpoint.id)).where(
                IntegrationEndpoint.integration_type == IntegrationType.VMWARE,
                IntegrationEndpoint.enabled.is_(True),
            )
        )
    ).scalar() or 0

    metrics = {
        "datacenters": dc_count,
        "network_devices": device_count,
        "cisco_juniper_devices": cisco_juniper,
        "ip_prefixes": prefix_count,
        "config_backups": backup_count,
        "sensors": sensor_count,
        "prtg_integrations": prtg_count,
        "vmware_integrations": vmware_count,
    }

    modules = []
    for cap in CAPABILITIES:
        cid = cap["id"]
        active = True
        if cid == "datacenters":
            active = dc_count > 0
        elif cid == "cisco_juniper":
            active = cisco_juniper > 0
        elif cid == "ipam":
            active = prefix_count > 0
        elif cid == "snmp":
            active = sensor_count > 0
        elif cid == "config_backup":
            active = backup_count > 0 or cisco_juniper > 0
        elif cid == "prtg":
            active = prtg_count > 0
        elif cid == "vmware":
            active = vmware_count > 0
        modules.append({**cap, "enabled": True, "active": active})

    return {"modules": modules, "metrics": metrics}
