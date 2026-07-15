import asyncio
import re

from app.vendors.base import BaseVendorAdapter, DeviceInfo, MetricReading


class FortinetAdapter(BaseVendorAdapter):
    vendor = "fortinet"

    async def collect_snmp(self, host: str, community: str, port: int = 161) -> DeviceInfo:
        from app.services.snmp_collector import snmp_get_bulk

        oids = {
            "sysName": "1.3.6.1.2.1.1.5.0",
            "sysDescr": "1.3.6.1.2.1.1.1.0",
            "fgSysSerial": "1.3.6.1.4.1.12356.101.4.1.2.0",
            "fgSysVersion": "1.3.6.1.4.1.12356.101.4.1.3.0",
        }
        data = await asyncio.to_thread(snmp_get_bulk, host, community, oids, port)
        return DeviceInfo(
            hostname=data.get("sysName", host),
            model=self._parse_model(data.get("sysDescr", "")),
            serial_number=data.get("fgSysSerial"),
            os_version=data.get("fgSysVersion"),
            raw=data,
        )

    async def collect_ssh(self, host: str, username: str, password: str, port: int = 22) -> DeviceInfo:
        from app.services.ssh_connector import run_ssh_command

        output = await asyncio.to_thread(
            run_ssh_command, host, username, password, "get system status", port
        )
        hostname_match = re.search(r"Hostname: (\S+)", output)
        version_match = re.search(r"Version: (.+)", output)
        serial_match = re.search(r"Serial-Number: (\S+)", output)
        return DeviceInfo(
            hostname=hostname_match.group(1) if hostname_match else host,
            serial_number=serial_match.group(1) if serial_match else None,
            os_version=version_match.group(1).strip() if version_match else None,
            raw={"system_status": output},
        )

    async def collect_netconf(self, host: str, username: str, password: str, port: int = 830) -> DeviceInfo:
        return DeviceInfo(
            hostname=host,
            raw={"note": "Fortinet NETCONF support varies by model; use REST API when available"},
        )

    async def collect_rest(self, host: str, token: str, port: int = 443) -> DeviceInfo:
        from app.services.rest_api_connector import rest_get

        data = await rest_get(host, "/api/v2/monitor/system/status", token, port, verify_ssl=False)
        results = data.get("results", {}) if isinstance(data, dict) else {}
        return DeviceInfo(
            hostname=results.get("hostname", host),
            model=results.get("model"),
            serial_number=results.get("serial"),
            os_version=results.get("version"),
            raw=data if isinstance(data, dict) else {"response": str(data)},
        )

    async def get_metrics_snmp(self, host: str, community: str, port: int = 161) -> list[MetricReading]:
        from app.services.snmp_collector import snmp_get_bulk

        oids = {
            "cpu": "1.3.6.1.4.1.12356.101.4.1.3.0",
            "mem": "1.3.6.1.4.1.12356.101.4.1.4.0",
            "sessions": "1.3.6.1.4.1.12356.101.4.1.8.0",
        }
        data = await asyncio.to_thread(snmp_get_bulk, host, community, oids, port)
        metrics: list[MetricReading] = []
        if "mem" in data:
            try:
                metrics.append(MetricReading("memory_usage", float(data["mem"]), "%"))
            except ValueError:
                pass
        if "sessions" in data:
            try:
                metrics.append(MetricReading("active_sessions", float(data["sessions"]), "count"))
            except ValueError:
                pass
        return metrics

    def _parse_model(self, descr: str) -> str | None:
        match = re.search(r"(FortiGate-\S+)", descr)
        return match.group(1) if match else None
