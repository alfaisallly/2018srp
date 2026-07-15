"""Parse Excel files for DCMS asset import."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from openpyxl import Workbook, load_workbook

ASSET_HEADERS = {
    "datacenter": ("datacenter", "مركز البيانات", "dc", "datacenter_name"),
    "asset_type": ("asset_type", "نوع الأصل", "type", "النوع"),
    "name": ("name", "الاسم", "device_name"),
    "hostname": ("hostname", "host", "اسم المضيف"),
    "ip_address": ("ip_address", "ip", "address", "عنوان_ip", "العنوان"),
    "vendor": ("vendor", "المورّد", "manufacturer"),
    "protocol": ("protocol", "البروتوكول"),
    "community": ("community", "snmp_community"),
    "username": ("username", "user", "اسم المستخدم"),
    "password": ("password", "pass", "كلمة المرور"),
    "api_token": ("api_token", "token", "api"),
    "port": ("port", "المنفذ"),
    "os_type": ("os_type", "os", "نظام التشغيل"),
    "server_role": ("server_role", "role", "الدور"),
    "storage_type": ("storage_type", "نوع_التخزين"),
    "model": ("model", "الطراز"),
    "notes": ("notes", "ملاحظات"),
}

LINK_HEADERS = {
    "datacenter": ("datacenter", "مركز البيانات", "dc"),
    "from_name": ("from_name", "from", "من", "source", "المصدر"),
    "to_name": ("to_name", "to", "إلى", "target", "الهدف"),
    "from_ip": ("from_ip", "source_ip"),
    "to_ip": ("to_ip", "target_ip"),
    "label": ("label", "الوصف", "description"),
}

ASSET_TYPE_MAP = {
    "device": "device",
    "network": "device",
    "شبكة": "device",
    "جهاز": "device",
    "switch": "device",
    "router": "device",
    "firewall": "device",
    "server": "server",
    "سيرفر": "server",
    "srv": "server",
    "storage": "storage",
    "تخزين": "storage",
    "san": "storage",
    "nas": "storage",
}

VENDOR_MAP = {
    "cisco": "cisco",
    "جونيبر": "juniper",
    "juniper": "juniper",
    "fortinet": "fortinet",
    "فورتينت": "fortinet",
    "pure": "pure_storage",
    "pure_storage": "pure_storage",
    "pure storage": "pure_storage",
    "netapp": "netapp",
    "dell": "dell_emc",
    "dell_emc": "dell_emc",
    "hpe": "hpe",
    "qnap": "qnap",
    "synology": "synology",
}


@dataclass
class ParsedAsset:
    datacenter: str
    asset_type: str
    name: str
    hostname: str
    ip_address: str
    vendor: str | None = None
    protocol: str | None = None
    community: str | None = None
    username: str | None = None
    password: str | None = None
    api_token: str | None = None
    port: int | None = None
    os_type: str | None = None
    server_role: str | None = None
    storage_type: str | None = None
    model: str | None = None
    notes: str | None = None
    row: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ParsedLink:
    datacenter: str
    from_ref: str
    to_ref: str
    label: str | None = None
    row: int = 0


@dataclass
class ExcelParseResult:
    assets: list[ParsedAsset]
    links: list[ParsedLink]
    datacenters: list[str]
    errors: list[str]
    summary: dict[str, int]


def _normalize_header(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "_")


def _map_headers(row: list, header_map: dict) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row):
        norm = _normalize_header(cell)
        for field_name, aliases in header_map.items():
            if norm in aliases and field_name not in mapping:
                mapping[field_name] = idx
    return mapping


def _cell(row: list, mapping: dict[str, int], key: str) -> str | None:
    idx = mapping.get(key)
    if idx is None or idx >= len(row):
        return None
    val = row[idx]
    if val is None:
        return None
    return str(val).strip() or None


def _parse_port(val: str | None) -> int | None:
    if not val:
        return None
    try:
        return int(float(val))
    except ValueError:
        return None


def parse_excel_bytes(content: bytes) -> ExcelParseResult:
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    assets: list[ParsedAsset] = []
    links: list[ParsedLink] = []
    errors: list[str] = []

    asset_sheet = None
    link_sheet = None
    for name in wb.sheetnames:
        lower = name.lower()
        if lower in ("assets", "devices", "الأصول", "الاجهزة", "أجهزة"):
            asset_sheet = wb[name]
        elif lower in ("links", "topology", "الروابط", "المخطط", "topo"):
            link_sheet = wb[name]

    if asset_sheet is None:
        asset_sheet = wb[wb.sheetnames[0]]
    if link_sheet is None and len(wb.sheetnames) > 1:
        link_sheet = wb[wb.sheetnames[1]]

    rows = list(asset_sheet.iter_rows(values_only=True))
    if not rows:
        return ExcelParseResult([], [], [], ["ملف Excel فارغ"], {})

    header_mapping = _map_headers(list(rows[0]), ASSET_HEADERS)
    if "name" not in header_mapping and "ip_address" not in header_mapping:
        errors.append("ورقة الأصول: يجب وجود أعمدة name أو ip_address")

    for i, row in enumerate(rows[1:], start=2):
        row = list(row)
        if not any(row):
            continue
        dc = _cell(row, header_mapping, "datacenter") or "Default-DC"
        name = _cell(row, header_mapping, "name")
        ip = _cell(row, header_mapping, "ip_address")
        if not name and not ip:
            continue
        if not ip:
            errors.append(f"صف {i}: عنوان IP مفقود")
            continue

        raw_type = (_cell(row, header_mapping, "asset_type") or "device").lower()
        asset_type = ASSET_TYPE_MAP.get(raw_type, "device")
        hostname = _cell(row, header_mapping, "hostname") or (name or ip).lower().replace(" ", "-")
        name = name or hostname

        vendor_raw = _cell(row, header_mapping, "vendor")
        vendor_key = (vendor_raw or "").lower()
        vendor = VENDOR_MAP.get(vendor_key) or (vendor_key if vendor_key else None)

        asset = ParsedAsset(
            datacenter=dc,
            asset_type=asset_type,
            name=name,
            hostname=hostname,
            ip_address=ip,
            vendor=vendor,
            protocol=(_cell(row, header_mapping, "protocol") or "snmp").lower(),
            community=_cell(row, header_mapping, "community"),
            username=_cell(row, header_mapping, "username"),
            password=_cell(row, header_mapping, "password"),
            api_token=_cell(row, header_mapping, "api_token"),
            port=_parse_port(_cell(row, header_mapping, "port")),
            os_type=(_cell(row, header_mapping, "os_type") or "linux").lower(),
            server_role=(_cell(row, header_mapping, "server_role") or "other").lower(),
            storage_type=(_cell(row, header_mapping, "storage_type") or "san").lower(),
            model=_cell(row, header_mapping, "model"),
            notes=_cell(row, header_mapping, "notes"),
            row=i,
        )
        assets.append(asset)

    if link_sheet:
        lrows = list(link_sheet.iter_rows(values_only=True))
        if lrows:
            link_map = _map_headers(list(lrows[0]), LINK_HEADERS)
            for i, row in enumerate(lrows[1:], start=2):
                row = list(row)
                if not any(row):
                    continue
                dc = _cell(row, link_map, "datacenter") or "Default-DC"
                from_ref = _cell(row, link_map, "from_name") or _cell(row, link_map, "from_ip")
                to_ref = _cell(row, link_map, "to_name") or _cell(row, link_map, "to_ip")
                if from_ref and to_ref:
                    links.append(
                        ParsedLink(
                            datacenter=dc,
                            from_ref=from_ref,
                            to_ref=to_ref,
                            label=_cell(row, link_map, "label"),
                            row=i,
                        )
                    )

    datacenters = sorted({a.datacenter for a in assets} | {l.datacenter for l in links})
    summary = {
        "total": len(assets),
        "devices": sum(1 for a in assets if a.asset_type == "device"),
        "servers": sum(1 for a in assets if a.asset_type == "server"),
        "storage": sum(1 for a in assets if a.asset_type == "storage"),
        "links": len(links),
        "datacenters": len(datacenters),
    }
    return ExcelParseResult(assets, links, datacenters, errors, summary)


def build_topology(assets: list[ParsedAsset], links: list[ParsedLink], dc_name: str, asset_ids: dict[str, str]) -> dict:
    """Build vis.js topology for a datacenter."""
    nodes = [{"id": f"dc-{dc_name}", "label": dc_name, "shape": "box", "color": "#3b82f6"}]
    edges = []

    dc_assets = [a for a in assets if a.datacenter == dc_name]
    for asset in dc_assets:
        node_id = asset_ids.get(asset.ip_address) or asset_ids.get(asset.name) or f"asset-{asset.name}"
        color = {"device": "#049fd9", "server": "#8b5cf6", "storage": "#fa6200"}.get(asset.asset_type, "#94a3b8")
        nodes.append({"id": node_id, "label": f"{asset.name}\n{asset.ip_address}", "color": color})
        edges.append({"from": f"dc-{dc_name}", "to": node_id})

    dc_links = [l for l in links if l.datacenter == dc_name]
    if dc_links:
        edges = []
        for link in dc_links:
            from_id = asset_ids.get(link.from_ref) or f"ref-{link.from_ref}"
            to_id = asset_ids.get(link.to_ref) or f"ref-{link.to_ref}"
            if not any(n["id"] == from_id for n in nodes):
                nodes.append({"id": from_id, "label": link.from_ref, "color": "#64748b"})
            if not any(n["id"] == to_id for n in nodes):
                nodes.append({"id": to_id, "label": link.to_ref, "color": "#64748b"})
            edges.append({"from": from_id, "to": to_id, "label": link.label or ""})

    return {"nodes": nodes, "edges": edges}


def generate_template_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Assets"
    ws.append([
        "datacenter", "asset_type", "name", "hostname", "ip_address", "vendor",
        "protocol", "community", "username", "password", "api_token", "port",
        "os_type", "server_role", "storage_type", "model", "notes",
    ])
    ws.append([
        "DC-MOROOR-01", "device", "MR-Core-SW-01", "mr-core-sw-01", "172.16.10.1",
        "cisco", "snmp", "public", "", "", "", "161", "", "", "", "", "",
    ])
    ws.append([
        "DC-MOROOR-01", "server", "MR-APP-SRV-01", "mr-app-srv-01", "172.16.10.10",
        "", "ssh", "", "admin", "pass", "", "22", "linux", "application", "", "", "",
    ])
    ws.append([
        "DC-MOI-01", "storage", "MOI-Pure-R40-01", "moi-pure-r40-01", "172.16.20.20",
        "pure_storage", "rest", "", "", "", "pure-api-token", "443", "", "", "san", "FlashArray //R40", "",
    ])
    ws2 = wb.create_sheet("Links")
    ws2.append(["datacenter", "from_name", "to_name", "label"])
    ws2.append(["DC-MOROOR-01", "MR-Core-SW-01", "MR-APP-SRV-01", "uplink"])
    ws2.append(["DC-MOROOR-01", "MR-Core-SW-01", "MR-Pure-R40-01", "storage"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
