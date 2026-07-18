from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceInfo:
    hostname: str
    model: str | None = None
    serial_number: str | None = None
    os_version: str | None = None
    uptime_seconds: int | None = None
    interfaces: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricReading:
    name: str
    value: float
    unit: str | None = None


class BaseVendorAdapter:
    vendor: str = "generic"

    async def collect_snmp(self, host: str, community: str, port: int = 161) -> DeviceInfo:
        raise NotImplementedError

    async def collect_ssh(self, host: str, username: str, password: str, port: int = 22) -> DeviceInfo:
        raise NotImplementedError

    async def collect_netconf(self, host: str, username: str, password: str, port: int = 830) -> DeviceInfo:
        raise NotImplementedError

    async def collect_rest(self, host: str, token: str, port: int = 443) -> DeviceInfo:
        raise NotImplementedError

    async def get_metrics_snmp(self, host: str, community: str, port: int = 161) -> list[MetricReading]:
        raise NotImplementedError
