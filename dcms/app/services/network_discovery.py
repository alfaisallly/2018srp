import asyncio
import ipaddress
import re
from dataclasses import dataclass

from app.config import get_settings
from app.models import VendorType
from app.services.snmp_collector import _async_snmp_get

settings = get_settings()

SYS_DESCR_OID = "1.3.6.1.2.1.1.1.0"
SYS_NAME_OID = "1.3.6.1.2.1.1.5.0"


@dataclass
class DiscoveredDevice:
    ip_address: str
    hostname: str
    sys_descr: str
    vendor: VendorType
    model: str | None = None


def parse_ip_range(cidr: str | None, start_ip: str | None, end_ip: str | None) -> list[str]:
    if cidr:
        network = ipaddress.ip_network(cidr, strict=False)
        return [str(host) for host in network.hosts()]
    if start_ip and end_ip:
        start = int(ipaddress.ip_address(start_ip))
        end = int(ipaddress.ip_address(end_ip))
        if start > end:
            start, end = end, start
        return [str(ipaddress.ip_address(i)) for i in range(start, end + 1)]
    raise ValueError("Provide cidr or start_ip + end_ip")


def detect_vendor(sys_descr: str) -> tuple[VendorType, str | None]:
    descr_lower = sys_descr.lower()
    if "cisco" in descr_lower:
        match = re.search(r"cisco (\S+)", sys_descr, re.IGNORECASE)
        return VendorType.CISCO, match.group(1) if match else None
    if "juniper" in descr_lower:
        match = re.search(r"Juniper Networks, Inc\. (\S+)", sys_descr)
        return VendorType.JUNIPER, match.group(1) if match else None
    if "fortinet" in descr_lower or "fortigate" in descr_lower:
        match = re.search(r"(FortiGate-\S+)", sys_descr, re.IGNORECASE)
        return VendorType.FORTINET, match.group(1) if match else None
    return VendorType.GENERIC, None


async def _probe_host(ip: str, community: str, port: int) -> DiscoveredDevice | None:
    sys_descr = await _async_snmp_get(ip, community, SYS_DESCR_OID, port)
    if not sys_descr:
        return None
    sys_name = await _async_snmp_get(ip, community, SYS_NAME_OID, port)
    vendor, model = detect_vendor(sys_descr)
    hostname = sys_name or ip
    return DiscoveredDevice(
        ip_address=ip,
        hostname=hostname,
        sys_descr=sys_descr[:256],
        vendor=vendor,
        model=model,
    )


async def discover_network(
    cidr: str | None = None,
    start_ip: str | None = None,
    end_ip: str | None = None,
    community: str = "public",
    port: int = 161,
    max_hosts: int = 254,
    concurrency: int = 50,
) -> list[DiscoveredDevice]:
    hosts = parse_ip_range(cidr, start_ip, end_ip)
    if len(hosts) > max_hosts:
        hosts = hosts[:max_hosts]

    semaphore = asyncio.Semaphore(concurrency)
    results: list[DiscoveredDevice] = []

    async def scan(ip: str) -> None:
        async with semaphore:
            try:
                device = await _probe_host(ip, community, port)
                if device:
                    results.append(device)
            except Exception:
                pass

    await asyncio.gather(*(scan(ip) for ip in hosts))
    results.sort(key=lambda d: ipaddress.ip_address(d.ip_address))
    return results
