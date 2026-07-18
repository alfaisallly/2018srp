import asyncio
import re
from typing import Any

from app.vendors.base import BaseVendorAdapter, DeviceInfo, MetricReading


class CiscoAdapter(BaseVendorAdapter):
    vendor = "cisco"

    async def collect_snmp(self, host: str, community: str, port: int = 161) -> DeviceInfo:
        from app.services.snmp_collector import snmp_get_bulk

        oids = {
            "sysName": "1.3.6.1.2.1.1.5.0",
            "sysDescr": "1.3.6.1.2.1.1.1.0",
            "sysUpTime": "1.3.6.1.2.1.1.3.0",
        }
        data = await asyncio.to_thread(snmp_get_bulk, host, community, oids, port)
        descr = data.get("sysDescr", "")
        model = self._parse_model(descr)
        uptime = int(data.get("sysUpTime", "0").split()[0]) // 100 if data.get("sysUpTime") else None
        return DeviceInfo(
            hostname=data.get("sysName", host),
            model=model,
            os_version=descr[:128] if descr else None,
            uptime_seconds=uptime,
            raw=data,
        )

    async def collect_ssh(self, host: str, username: str, password: str, port: int = 22) -> DeviceInfo:
        from app.services.ssh_connector import run_ssh_command

        output = await asyncio.to_thread(
            run_ssh_command, host, username, password, "show version", port
        )
        hostname_match = re.search(r"(\S+) uptime is", output)
        model_match = re.search(r"cisco (\S+)", output, re.IGNORECASE)
        serial_match = re.search(r"Processor board ID (\S+)", output)
        return DeviceInfo(
            hostname=hostname_match.group(1) if hostname_match else host,
            model=model_match.group(1) if model_match else None,
            serial_number=serial_match.group(1) if serial_match else None,
            os_version=output.split("\n")[0][:128] if output else None,
            raw={"show_version": output},
        )

    async def collect_netconf(self, host: str, username: str, password: str, port: int = 830) -> DeviceInfo:
        from app.services.netconf_connector import netconf_get

        xml = await asyncio.to_thread(
            netconf_get, host, username, password, "<filter><platform xmlns='http://cisco.com/ns/yang/Cisco-IOS-XE-native'/></filter>", port
        )
        return DeviceInfo(hostname=host, raw={"netconf": xml[:2000]})

    async def collect_rest(self, host: str, token: str, port: int = 443) -> DeviceInfo:
        from app.services.rest_api_connector import rest_get

        data = await rest_get(host, "/dna/intent/api/v1/network-device", token, port)
        device = (data.get("response") or [{}])[0] if isinstance(data, dict) else {}
        return DeviceInfo(
            hostname=device.get("hostname", host),
            model=device.get("platformId"),
            serial_number=device.get("serialNumber"),
            os_version=device.get("softwareVersion"),
            raw=data if isinstance(data, dict) else {"response": str(data)},
        )

    async def get_metrics_snmp(self, host: str, community: str, port: int = 161) -> list[MetricReading]:
        from app.services.snmp_collector import snmp_get_bulk

        oids = {
            "cpu": "1.3.6.1.4.1.9.9.109.1.1.1.1.5.1",
            "memory_used": "1.3.6.1.4.1.9.9.48.1.1.1.6.1",
        }
        data = await asyncio.to_thread(snmp_get_bulk, host, community, oids, port)
        metrics: list[MetricReading] = []
        if "cpu" in data:
            metrics.append(MetricReading("cpu_utilization", float(data["cpu"]), "%"))
        if "memory_used" in data:
            metrics.append(MetricReading("memory_used", float(data["memory_used"]), "bytes"))
        return metrics

    def _parse_model(self, descr: str) -> str | None:
        match = re.search(r"cisco (\S+)", descr, re.IGNORECASE)
        return match.group(1) if match else None
