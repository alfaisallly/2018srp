"""Parse SNMP IF-MIB, CDP/LLDP neighbors, and VLAN tables into inventory structures."""

from dataclasses import dataclass, field

IF_OPER_STATUS = {
    "1": "up",
    "2": "down",
    "3": "testing",
    "4": "unknown",
    "5": "dormant",
    "6": "notPresent",
    "7": "lowerLayerDown",
}

IF_ADMIN_STATUS = {
    "1": "up",
    "2": "down",
    "3": "testing",
}

IF_TYPE_ETHERNET = {"6", "117", "135", "136"}


@dataclass
class ParsedInterface:
    if_index: int
    name: str
    oper_status: str
    admin_status: str
    speed_mbps: int
    mtu: int | None = None
    neighbor_hostname: str | None = None
    neighbor_port: str | None = None
    access_vlan: int | None = None
    trunk_vlans: list[int] = field(default_factory=list)
    vlan_mode: str = "access"


@dataclass
class ParsedVlan:
    vlan_id: int
    name: str


@dataclass
class SnmpInventory:
    interfaces: list[ParsedInterface] = field(default_factory=list)
    vlans: list[ParsedVlan] = field(default_factory=list)
    source: str = "snmp"


def _index_suffix(oid: str, base: str) -> str | None:
    if not oid.startswith(base + "."):
        return None
    return oid[len(base) + 1 :]


def _mbps_from_speed(speed_raw: str | None, high_speed_raw: str | None) -> int:
    if high_speed_raw and high_speed_raw.isdigit() and int(high_speed_raw) > 0:
        return int(high_speed_raw)
    if speed_raw and speed_raw.isdigit():
        bps = int(speed_raw)
        if bps >= 1_000_000:
            return bps // 1_000_000
        if bps > 0:
            return max(1, bps // 1_000_000)
    return 1000


def parse_if_table(walk_data: dict[str, str]) -> dict[int, dict]:
    bases = {
        "descr": "1.3.6.1.2.1.2.2.1.2",
        "type": "1.3.6.1.2.1.2.2.1.3",
        "speed": "1.3.6.1.2.1.2.2.1.5",
        "admin": "1.3.6.1.2.1.2.2.1.7",
        "oper": "1.3.6.1.2.1.2.2.1.8",
        "mtu": "1.3.6.1.2.1.2.2.1.4",
        "high_speed": "1.3.6.1.2.1.31.1.1.1.15",
    }
    rows: dict[int, dict] = {}
    for oid, value in walk_data.items():
        for key, base in bases.items():
            suffix = _index_suffix(oid, base)
            if suffix is None or "." in suffix:
                continue
            try:
                idx = int(suffix)
            except ValueError:
                continue
            rows.setdefault(idx, {})[key] = value
    return rows


def parse_cdp_neighbors(walk_data: dict[str, str]) -> dict[int, dict]:
    device_base = "1.3.6.1.4.1.9.9.23.1.2.1.1.6"
    port_base = "1.3.6.1.4.1.9.9.23.1.2.1.1.7"
    neighbors: dict[int, dict] = {}
    for oid, value in walk_data.items():
        if oid.startswith(device_base + "."):
            parts = oid.split(".")
            if len(parts) >= 2:
                if_index = int(parts[-2])
                neighbors.setdefault(if_index, {})["hostname"] = value.strip()
        elif oid.startswith(port_base + "."):
            parts = oid.split(".")
            if len(parts) >= 2:
                if_index = int(parts[-2])
                neighbors.setdefault(if_index, {})["port"] = value.strip()
    return neighbors


def parse_lldp_neighbors(walk_data: dict[str, str]) -> dict[int, dict]:
    sys_base = "1.0.8802.1.1.2.1.4.1.1.9"
    port_base = "1.0.8802.1.1.2.1.4.2.1.7"
    neighbors: dict[int, dict] = {}
    for oid, value in walk_data.items():
        if oid.startswith(sys_base + "."):
            parts = oid.split(".")
            if len(parts) >= 2:
                if_index = int(parts[-2])
                neighbors.setdefault(if_index, {})["hostname"] = value.strip()
        elif oid.startswith(port_base + "."):
            parts = oid.split(".")
            if len(parts) >= 2:
                if_index = int(parts[-2])
                neighbors.setdefault(if_index, {})["port"] = value.strip()
    return neighbors


def parse_dot1q_vlans(walk_data: dict[str, str]) -> list[ParsedVlan]:
    name_base = "1.3.6.1.2.1.17.7.1.4.3.1.1"
    vlans: list[ParsedVlan] = []
    for oid, value in walk_data.items():
        suffix = _index_suffix(oid, name_base)
        if suffix and suffix.isdigit():
            vid = int(suffix)
            if 1 <= vid <= 4094:
                vlans.append(ParsedVlan(vlan_id=vid, name=value.strip() or f"VLAN-{vid}"))
    return sorted(vlans, key=lambda v: v.vlan_id)


def parse_cisco_port_vlans(walk_data: dict[str, str]) -> dict[int, int]:
    base = "1.3.6.1.4.1.9.9.68.1.2.2.1.2"
    mapping: dict[int, int] = {}
    for oid, value in walk_data.items():
        suffix = _index_suffix(oid, base)
        if suffix and suffix.isdigit() and value.isdigit():
            mapping[int(suffix)] = int(value)
    return mapping


def build_inventory(
    if_rows: dict[int, dict],
    neighbors: dict[int, dict],
    vlans: list[ParsedVlan],
    port_vlans: dict[int, int] | None = None,
) -> SnmpInventory:
    port_vlans = port_vlans or {}
    interfaces: list[ParsedInterface] = []
    for idx, row in sorted(if_rows.items()):
        name = row.get("descr", f"if{idx}")
        if_type = row.get("type", "")
        if if_type and if_type not in IF_TYPE_ETHERNET and "loopback" in name.lower():
            continue
        if name.lower().startswith("null") or name.lower() == "lo0":
            continue

        oper = IF_OPER_STATUS.get(row.get("oper", "4"), "unknown")
        admin = IF_ADMIN_STATUS.get(row.get("admin", "2"), "down")
        speed = _mbps_from_speed(row.get("speed"), row.get("high_speed"))
        neighbor = neighbors.get(idx, {})
        access_vlan = port_vlans.get(idx)
        vlan_mode = "access" if access_vlan else "unknown"

        interfaces.append(
            ParsedInterface(
                if_index=idx,
                name=name,
                oper_status=oper if oper in ("up", "down") else "down",
                admin_status=admin,
                speed_mbps=speed,
                mtu=int(row["mtu"]) if row.get("mtu", "").isdigit() else None,
                neighbor_hostname=neighbor.get("hostname"),
                neighbor_port=neighbor.get("port"),
                access_vlan=access_vlan if access_vlan and access_vlan < 4095 else None,
                vlan_mode=vlan_mode,
            )
        )
    return SnmpInventory(interfaces=interfaces, vlans=vlans)
