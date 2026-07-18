import asyncio
import re

from app.vendors.base import BaseVendorAdapter, DeviceInfo


class PaloAltoAdapter(BaseVendorAdapter):
    vendor = "palo_alto"

    async def collect_ssh(self, host: str, username: str, password: str, port: int = 22) -> DeviceInfo:
        from app.services.ssh_connector import run_ssh_command

        output = await asyncio.to_thread(
            run_ssh_command, host, username, password, "show system info", port
        )
        hostname = host
        model = None
        serial = None
        os_version = None
        for line in output.splitlines():
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "hostname":
                hostname = val
            elif key == "model":
                model = val
            elif key == "serial":
                serial = val
            elif key == "sw-version":
                os_version = val
        if not model:
            m = re.search(r"model:\s*(\S+)", output, re.IGNORECASE)
            model = m.group(1) if m else None
        return DeviceInfo(
            hostname=hostname,
            model=model,
            serial_number=serial,
            os_version=os_version,
            raw={"show_system_info": output[:2000]},
        )
