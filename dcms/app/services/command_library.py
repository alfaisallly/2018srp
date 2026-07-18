"""Built-in CLI command library for Cisco, Juniper, and Palo Alto devices."""

from app.models import VendorType

CommandEntry = dict

COMMAND_LIBRARY: list[CommandEntry] = [
    # Cisco — show
    {"id": "cisco_show_version", "vendor": VendorType.CISCO, "category": "show", "name": "show_version",
     "label_ar": "عرض الإصدار", "label_en": "Show version", "command": "show version", "mode": "exec"},
    {"id": "cisco_show_run", "vendor": VendorType.CISCO, "category": "show", "name": "show_running_config",
     "label_ar": "الإعداد الجاري", "label_en": "Running config", "command": "show running-config", "mode": "exec"},
    {"id": "cisco_show_int_status", "vendor": VendorType.CISCO, "category": "show", "name": "show_interfaces_status",
     "label_ar": "حالة المنافذ", "label_en": "Interface status", "command": "show interfaces status", "mode": "exec"},
    {"id": "cisco_show_int_brief", "vendor": VendorType.CISCO, "category": "show", "name": "show_ip_int_brief",
     "label_ar": "ملخص IP", "label_en": "IP interface brief", "command": "show ip interface brief", "mode": "exec"},
    {"id": "cisco_show_vlan", "vendor": VendorType.CISCO, "category": "show", "name": "show_vlan",
     "label_ar": "VLANs", "label_en": "VLANs", "command": "show vlan brief", "mode": "exec"},
    {"id": "cisco_show_cdp", "vendor": VendorType.CISCO, "category": "show", "name": "show_cdp_neighbors",
     "label_ar": "جيران CDP", "label_en": "CDP neighbors", "command": "show cdp neighbors detail", "mode": "exec"},
    {"id": "cisco_show_mac", "vendor": VendorType.CISCO, "category": "show", "name": "show_mac_table",
     "label_ar": "جدول MAC", "label_en": "MAC address table", "command": "show mac address-table", "mode": "exec"},
    {"id": "cisco_show_spanning", "vendor": VendorType.CISCO, "category": "show", "name": "show_spanning_tree",
     "label_ar": "Spanning Tree", "label_en": "Spanning tree", "command": "show spanning-tree summary", "mode": "exec"},
    # Juniper — show
    {"id": "juniper_show_version", "vendor": VendorType.JUNIPER, "category": "show", "name": "show_version",
     "label_ar": "عرض الإصدار", "label_en": "Show version", "command": "show version", "mode": "exec"},
    {"id": "juniper_show_config", "vendor": VendorType.JUNIPER, "category": "show", "name": "show_configuration",
     "label_ar": "الإعداد الحالي", "label_en": "Configuration", "command": "show configuration | display set", "mode": "exec"},
    {"id": "juniper_show_int", "vendor": VendorType.JUNIPER, "category": "show", "name": "show_interfaces",
     "label_ar": "المنافذ", "label_en": "Interfaces", "command": "show interfaces terse", "mode": "exec"},
    {"id": "juniper_show_vlan", "vendor": VendorType.JUNIPER, "category": "show", "name": "show_vlans",
     "label_ar": "VLANs", "label_en": "VLANs", "command": "show vlans", "mode": "exec"},
    {"id": "juniper_show_lldp", "vendor": VendorType.JUNIPER, "category": "show", "name": "show_lldp",
     "label_ar": "جيران LLDP", "label_en": "LLDP neighbors", "command": "show lldp neighbors", "mode": "exec"},
    {"id": "juniper_show_route", "vendor": VendorType.JUNIPER, "category": "show", "name": "show_route",
     "label_ar": "جدول التوجيه", "label_en": "Routing table", "command": "show route summary", "mode": "exec"},
    {"id": "juniper_show_chassis", "vendor": VendorType.JUNIPER, "category": "show", "name": "show_chassis",
     "label_ar": "حالة Chassis", "label_en": "Chassis alarms", "command": "show chassis alarms", "mode": "exec"},
    # Palo Alto — show
    {"id": "pa_show_system", "vendor": VendorType.PALO_ALTO, "category": "show", "name": "show_system_info",
     "label_ar": "معلومات النظام", "label_en": "System info", "command": "show system info", "mode": "exec"},
    {"id": "pa_show_interfaces", "vendor": VendorType.PALO_ALTO, "category": "show", "name": "show_interfaces",
     "label_ar": "المنافذ", "label_en": "Interfaces", "command": "show interface all", "mode": "exec"},
    {"id": "pa_show_zones", "vendor": VendorType.PALO_ALTO, "category": "show", "name": "show_zones",
     "label_ar": "المناطق", "label_en": "Security zones", "command": "show zone", "mode": "exec"},
    {"id": "pa_show_rules", "vendor": VendorType.PALO_ALTO, "category": "show", "name": "show_security_rules",
     "label_ar": "قواعد الأمان", "label_en": "Security rules", "command": "show running security-policy", "mode": "exec"},
    {"id": "pa_show_sessions", "vendor": VendorType.PALO_ALTO, "category": "show", "name": "show_sessions",
     "label_ar": "الجلسات", "label_en": "Active sessions", "command": "show session info", "mode": "exec"},
    {"id": "pa_show_routes", "vendor": VendorType.PALO_ALTO, "category": "show", "name": "show_routes",
     "label_ar": "المسارات", "label_en": "Routes", "command": "show routing route", "mode": "exec"},
    {"id": "pa_show_ha", "vendor": VendorType.PALO_ALTO, "category": "show", "name": "show_ha",
     "label_ar": "HA", "label_en": "High availability", "command": "show high-availability state", "mode": "exec"},
    {"id": "pa_show_arp", "vendor": VendorType.PALO_ALTO, "category": "show", "name": "show_arp",
     "label_ar": "جدول ARP", "label_en": "ARP table", "command": "show arp all", "mode": "exec"},
]


def list_commands(vendor: VendorType | None = None, category: str | None = None) -> list[dict]:
    items = COMMAND_LIBRARY
    if vendor:
        items = [c for c in items if c["vendor"] == vendor]
    if category:
        items = [c for c in items if c["category"] == category]
    return [
        {
            "id": c["id"],
            "vendor": c["vendor"].value,
            "category": c["category"],
            "name": c["name"],
            "label_ar": c["label_ar"],
            "label_en": c["label_en"],
            "command": c["command"],
            "mode": c.get("mode", "exec"),
        }
        for c in items
    ]


def get_command(command_id: str) -> CommandEntry | None:
    return next((c for c in COMMAND_LIBRARY if c["id"] == command_id), None)
