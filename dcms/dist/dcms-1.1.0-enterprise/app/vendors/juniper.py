import asyncio
import re

from app.vendors.base import BaseVendorAdapter, DeviceInfo, MetricReading


class JuniperAdapter(BaseVendorAdapter):
    vendor = "juniper"

    async def collect_snmp(self, host: str, community: str, port: int = 161) -> DeviceInfo:
        from app.services.snmp_collector import snmp_get_bulk

        oids = {
            "sysName": "1.3.6.1.2.1.1.5.0",
            "sysDescr": "1.3.6.1.2.1.1.1.0",
            "jnxBoxSerial": "1.3.6.1.4.1.2636.3.1.13.0",
        }
        data = await asyncio.to_thread(snmp_get_bulk, host, community, oids, port)
        return DeviceInfo(
            hostname=data.get("sysName", host),
            model=self._parse_model(data.get("sysDescr", "")),
            serial_number=data.get("jnxBoxSerial"),
            os_version=data.get("sysDescr", "")[:128] or None,
            raw=data,
        )

    async def collect_ssh(self, host: str, username: str, password: str, port: int = 22) -> DeviceInfo:
        from app.services.ssh_connector import run_ssh_command

        output = await asyncio.to_thread(
            run_ssh_command, host, username, password, "show version", port
        )
        hostname_match = re.search(r"Hostname: (\S+)", output)
        model_match = re.search(r"Model: (\S+)", output)
        serial_match = re.search(r"Serial ID: (\S+)", output)
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
            netconf_get,
            host,
            username,
            password,
            "<system-information/>",
            port,
            device_params={"name": "junos"},
        )
        hostname_match = re.search(r"<host-name>([^<]+)</host-name>", xml)
        model_match = re.search(r"<model>([^<]+)</model>", xml)
        serial_match = re.search(r"<serial-number>([^<]+)</serial-number>", xml)
        return DeviceInfo(
            hostname=hostname_match.group(1) if hostname_match else host,
            model=model_match.group(1) if model_match else None,
            serial_number=serial_match.group(1) if serial_match else None,
            raw={"netconf": xml[:2000]},
        )

    async def collect_rest(self, host: str, token: str, port: int = 443) -> DeviceInfo:
        from app.services.rest_api_connector import rest_get

        data = await rest_get(host, "/api/health", token, port, verify_ssl=False)
        return DeviceInfo(hostname=host, raw=data if isinstance(data, dict) else {"response": str(data)})

    async def get_metrics_snmp(self, host: str, community: str, port: int = 161) -> list[MetricReading]:
        from app.services.snmp_collector import snmp_get_bulk

        oids = {
            "cpu": "1.3.6.1.4.1.2636.3.1.13.0",
            "buffer": "1.3.6.1.4.1.2636.3.4.1.3.0",
        }
        data = await asyncio.to_thread(snmp_get_bulk, host, community, oids, port)
        metrics: list[MetricReading] = []
        if "buffer" in data:
            try:
                metrics.append(MetricReading("buffer_utilization", float(data["buffer"]), "%"))
            except ValueError:
                pass
        return metrics

    def _parse_model(self, descr: str) -> str | None:
        match = re.search(r"Juniper Networks, Inc\. (\S+)", descr)
        return match.group(1) if match else None
