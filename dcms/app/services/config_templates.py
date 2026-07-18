"""Secure configuration template library for Cisco and Juniper devices."""

from jinja2 import Template, StrictUndefined
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConfigTemplate, VendorType

BUILTIN_TEMPLATES: list[dict] = [
    {
        "vendor": VendorType.CISCO,
        "category": "vlan",
        "name": "cisco_vlan_create",
        "description": "إنشاء VLAN جديدة على سويج Cisco IOS/XE",
        "variables": [
            {"name": "vlan_id", "label": "رقم VLAN", "type": "number", "required": True},
            {"name": "vlan_name", "label": "اسم VLAN", "type": "text", "required": True},
        ],
        "tags": ["vlan", "switch", "layer2"],
        "template_body": """vlan {{ vlan_id }}
 name {{ vlan_name }}
!
""",
    },
    {
        "vendor": VendorType.CISCO,
        "category": "port",
        "name": "cisco_trunk_port",
        "description": "تكوين منفذ Trunk على Cisco",
        "variables": [
            {"name": "interface", "label": "الواجهة", "type": "text", "required": True, "example": "GigabitEthernet1/0/1"},
            {"name": "allowed_vlans", "label": "VLANs المسموحة", "type": "text", "required": True, "example": "10,20,30"},
            {"name": "native_vlan", "label": "Native VLAN", "type": "number", "required": False, "example": "1"},
        ],
        "tags": ["port", "trunk", "switch"],
        "template_body": """interface {{ interface }}
 switchport mode trunk
 switchport trunk allowed vlan {{ allowed_vlans }}
{% if native_vlan %} switchport trunk native vlan {{ native_vlan }}
{% endif %} no shutdown
!
""",
    },
    {
        "vendor": VendorType.CISCO,
        "category": "port",
        "name": "cisco_access_port",
        "description": "تكوين منفذ Access مع VLAN",
        "variables": [
            {"name": "interface", "label": "الواجهة", "type": "text", "required": True},
            {"name": "access_vlan", "label": "VLAN", "type": "number", "required": True},
            {"name": "description", "label": "الوصف", "type": "text", "required": False},
        ],
        "tags": ["port", "access", "vlan"],
        "template_body": """interface {{ interface }}
{% if description %} description {{ description }}
{% endif %} switchport mode access
 switchport access vlan {{ access_vlan }}
 no shutdown
!
""",
    },
    {
        "vendor": VendorType.CISCO,
        "category": "routing",
        "name": "cisco_ospf_interface",
        "description": "تفعيل OSPF على واجهة Cisco",
        "variables": [
            {"name": "process_id", "label": "Process ID", "type": "number", "required": True},
            {"name": "interface", "label": "الواجهة", "type": "text", "required": True},
            {"name": "area", "label": "OSPF Area", "type": "number", "required": True},
        ],
        "tags": ["routing", "ospf"],
        "template_body": """router ospf {{ process_id }}
 network {{ interface }} area {{ area }}
!
""",
    },
    {
        "vendor": VendorType.CISCO,
        "category": "backup_link",
        "name": "cisco_backup_wireless_link",
        "description": "ربط خدمة بديلة لاسلكية للمواقع الفرعية (Cellular/WWAN backup)",
        "variables": [
            {"name": "interface", "label": "واجهة WWAN", "type": "text", "required": True, "example": "Cellular0/1/0"},
            {"name": "primary_track", "label": "Track للرابط الأساسي", "type": "number", "required": True, "example": "1"},
            {"name": "backup_route", "label": "مسار احتياطي", "type": "text", "required": True, "example": "0.0.0.0/0"},
            {"name": "backup_gw", "label": "Gateway احتياطي", "type": "text", "required": True},
        ],
        "tags": ["backup", "wireless", "branch", "failover"],
        "template_body": """track {{ primary_track }} interface {{ interface }} line-protocol
!
ip route {{ backup_route }} {{ backup_gw }} 250 track {{ primary_track }}
!
interface {{ interface }}
 ip address dhcp
 no shutdown
!
""",
    },
    {
        "vendor": VendorType.CISCO,
        "category": "backup_link",
        "name": "cisco_backup_fiber_failover",
        "description": "تكوين رابط احتياطي بالكابل الضوئي مع IP SLA",
        "variables": [
            {"name": "primary_interface", "label": "الواجهة الأساسية", "type": "text", "required": True},
            {"name": "backup_interface", "label": "الواجهة الاحتياطية", "type": "text", "required": True},
            {"name": "track_id", "label": "Track ID", "type": "number", "required": True},
            {"name": "sla_id", "label": "IP SLA ID", "type": "number", "required": True},
            {"name": "target_ip", "label": "IP للمراقبة", "type": "text", "required": True},
        ],
        "tags": ["backup", "fiber", "failover", "branch"],
        "template_body": """ip sla {{ sla_id }}
 icmp-echo {{ target_ip }}
 frequency 10
ip sla schedule {{ sla_id }} life forever start-time now
!
track {{ track_id }} ip sla {{ sla_id }} reachability
!
interface {{ backup_interface }}
 description BACKUP-FIBER-LINK
 no shutdown
!
interface {{ primary_interface }}
 description PRIMARY-FIBER-LINK
 no shutdown
!
""",
    },
    {
        "vendor": VendorType.JUNIPER,
        "category": "vlan",
        "name": "juniper_vlan_create",
        "description": "إنشاء VLAN على Juniper JunOS",
        "variables": [
            {"name": "vlan_name", "label": "اسم VLAN", "type": "text", "required": True},
            {"name": "vlan_id", "label": "رقم VLAN", "type": "number", "required": True},
            {"name": "description", "label": "الوصف", "type": "text", "required": False},
        ],
        "tags": ["vlan", "switch"],
        "template_body": """set vlans {{ vlan_name }} vlan-id {{ vlan_id }}
{% if description %}set vlans {{ vlan_name }} description "{{ description }}"
{% endif %}""",
    },
    {
        "vendor": VendorType.JUNIPER,
        "category": "port",
        "name": "juniper_trunk_port",
        "description": "تكوين منفذ Trunk على Juniper",
        "variables": [
            {"name": "interface", "label": "الواجهة", "type": "text", "required": True, "example": "ge-0/0/1"},
            {"name": "vlan_members", "label": "أعضاء VLAN", "type": "text", "required": True, "example": "vlan10 vlan20"},
        ],
        "tags": ["port", "trunk"],
        "template_body": """delete interfaces {{ interface }} unit 0
set interfaces {{ interface }} unit 0 family ethernet-switching interface-mode trunk
set interfaces {{ interface }} unit 0 family ethernet-switching vlan members [ {{ vlan_members }} ]
""",
    },
    {
        "vendor": VendorType.JUNIPER,
        "category": "port",
        "name": "juniper_access_port",
        "description": "تكوين منفذ Access على Juniper",
        "variables": [
            {"name": "interface", "label": "الواجهة", "type": "text", "required": True},
            {"name": "vlan_name", "label": "اسم VLAN", "type": "text", "required": True},
            {"name": "description", "label": "الوصف", "type": "text", "required": False},
        ],
        "tags": ["port", "access"],
        "template_body": """{% if description %}set interfaces {{ interface }} description "{{ description }}"
{% endif %}set interfaces {{ interface }} unit 0 family ethernet-switching interface-mode access
set interfaces {{ interface }} unit 0 family ethernet-switching vlan members {{ vlan_name }}
""",
    },
    {
        "vendor": VendorType.JUNIPER,
        "category": "routing",
        "name": "juniper_static_route",
        "description": "إضافة مسار ثابت على Juniper",
        "variables": [
            {"name": "destination", "label": "الوجهة", "type": "text", "required": True, "example": "0.0.0.0/0"},
            {"name": "next_hop", "label": "Next-hop", "type": "text", "required": True},
            {"name": "preference", "label": "Preference", "type": "number", "required": False, "example": "5"},
        ],
        "tags": ["routing", "static"],
        "template_body": """set routing-options static route {{ destination }} next-hop {{ next_hop }}{% if preference %} preference {{ preference }}{% endif %}
""",
    },
    {
        "vendor": VendorType.JUNIPER,
        "category": "backup_link",
        "name": "juniper_backup_wireless",
        "description": "ربط لاسلكي/LTE احتياطي للمواقع الفرعية على Juniper",
        "variables": [
            {"name": "primary_interface", "label": "الواجهة الأساسية", "type": "text", "required": True},
            {"name": "backup_interface", "label": "واجهة LTE/WWAN", "type": "text", "required": True},
            {"name": "track_name", "label": "اسم RPM Track", "type": "text", "required": True},
            {"name": "target_ip", "label": "IP للمراقبة", "type": "text", "required": True},
        ],
        "tags": ["backup", "wireless", "branch"],
        "template_body": """set services rpm probe {{ track_name }} test icmp-ping target address {{ target_ip }}
set services rpm probe {{ track_name }} test icmp-ping probe-count 3
set services rpm probe {{ track_name }} test icmp-ping probe-interval 5
set routing-options static route 0.0.0.0/0 qualified-next-hop {{ backup_interface }} preference 200
set interfaces {{ backup_interface }} description BACKUP-WIRELESS-LINK
set interfaces {{ primary_interface }} description PRIMARY-FIBER-LINK
""",
    },
    {
        "vendor": VendorType.JUNIPER,
        "category": "firewall",
        "name": "juniper_firewall_filter",
        "description": "إنشاء Firewall Filter على Juniper SRX/EX",
        "variables": [
            {"name": "filter_name", "label": "اسم الفلتر", "type": "text", "required": True},
            {"name": "term_name", "label": "اسم Term", "type": "text", "required": True},
            {"name": "source", "label": "المصدر", "type": "text", "required": True},
            {"name": "destination", "label": "الوجهة", "type": "text", "required": True},
            {"name": "action", "label": "الإجراء", "type": "text", "required": True, "example": "accept"},
        ],
        "tags": ["firewall", "security"],
        "template_body": """set firewall family inet filter {{ filter_name }} term {{ term_name }} from source-address {{ source }}
set firewall family inet filter {{ filter_name }} term {{ term_name }} from destination-address {{ destination }}
set firewall family inet filter {{ filter_name }} term {{ term_name }} then {{ action }}
""",
    },
    {
        "vendor": VendorType.PALO_ALTO,
        "category": "firewall",
        "name": "palo_alto_security_rule",
        "description": "إنشاء قاعدة أمان على Palo Alto",
        "variables": [
            {"name": "rule_name", "label": "اسم القاعدة", "type": "text", "required": True},
            {"name": "from_zone", "label": "منطقة المصدر", "type": "text", "required": True, "example": "trust"},
            {"name": "to_zone", "label": "منطقة الوجهة", "type": "text", "required": True, "example": "untrust"},
            {"name": "source", "label": "المصدر", "type": "text", "required": True, "example": "any"},
            {"name": "destination", "label": "الوجهة", "type": "text", "required": True, "example": "any"},
            {"name": "application", "label": "التطبيق", "type": "text", "required": True, "example": "any"},
            {"name": "service", "label": "الخدمة", "type": "text", "required": True, "example": "application-default"},
            {"name": "action", "label": "الإجراء", "type": "text", "required": True, "example": "allow"},
        ],
        "tags": ["firewall", "security", "policy"],
        "template_body": """set rulebase security rules {{ rule_name }} from {{ from_zone }}
set rulebase security rules {{ rule_name }} to {{ to_zone }}
set rulebase security rules {{ rule_name }} source {{ source }}
set rulebase security rules {{ rule_name }} destination {{ destination }}
set rulebase security rules {{ rule_name }} application {{ application }}
set rulebase security rules {{ rule_name }} service {{ service }}
set rulebase security rules {{ rule_name }} action {{ action }}
""",
    },
    {
        "vendor": VendorType.PALO_ALTO,
        "category": "firewall",
        "name": "palo_alto_nat_rule",
        "description": "قاعدة NAT على Palo Alto",
        "variables": [
            {"name": "rule_name", "label": "اسم القاعدة", "type": "text", "required": True},
            {"name": "from_zone", "label": "منطقة المصدر", "type": "text", "required": True},
            {"name": "to_zone", "label": "منطقة الوجهة", "type": "text", "required": True},
            {"name": "source", "label": "المصدر", "type": "text", "required": True},
            {"name": "destination", "label": "الوجهة", "type": "text", "required": True},
            {"name": "translated_address", "label": "العنوان المترجم", "type": "text", "required": True},
        ],
        "tags": ["firewall", "nat"],
        "template_body": """set rulebase nat rules {{ rule_name }} from {{ from_zone }}
set rulebase nat rules {{ rule_name }} to {{ to_zone }}
set rulebase nat rules {{ rule_name }} source {{ source }}
set rulebase nat rules {{ rule_name }} destination {{ destination }}
set rulebase nat rules {{ rule_name }} source-translation translated-address {{ translated_address }}
""",
    },
    {
        "vendor": VendorType.PALO_ALTO,
        "category": "routing",
        "name": "palo_alto_static_route",
        "description": "مسار ثابت على Palo Alto",
        "variables": [
            {"name": "route_name", "label": "اسم المسار", "type": "text", "required": True},
            {"name": "destination", "label": "الوجهة", "type": "text", "required": True, "example": "0.0.0.0/0"},
            {"name": "nexthop", "label": "Next-hop", "type": "text", "required": True},
            {"name": "interface", "label": "الواجهة", "type": "text", "required": False},
        ],
        "tags": ["routing", "static"],
        "template_body": """set network virtual-router default routing-table ip static-route {{ route_name }} destination {{ destination }}
set network virtual-router default routing-table ip static-route {{ route_name }} nexthop ip-address {{ nexthop }}
{% if interface %}set network virtual-router default routing-table ip static-route {{ route_name }} interface {{ interface }}
{% endif %}""",
    },
    {
        "vendor": VendorType.FORTINET,
        "category": "firewall",
        "name": "fortinet_policy",
        "description": "إنشاء سياسة Firewall على FortiGate",
        "variables": [
            {"name": "policy_id", "label": "رقم السياسة", "type": "number", "required": True},
            {"name": "srcintf", "label": "واجهة المصدر", "type": "text", "required": True},
            {"name": "dstintf", "label": "واجهة الوجهة", "type": "text", "required": True},
            {"name": "srcaddr", "label": "عنوان المصدر", "type": "text", "required": True},
            {"name": "dstaddr", "label": "عنوان الوجهة", "type": "text", "required": True},
            {"name": "service", "label": "الخدمة", "type": "text", "required": True},
            {"name": "action", "label": "الإجراء", "type": "text", "required": True, "example": "accept"},
        ],
        "tags": ["firewall", "policy"],
        "template_body": """config firewall policy
    edit {{ policy_id }}
        set srcintf "{{ srcintf }}"
        set dstintf "{{ dstintf }}"
        set srcaddr "{{ srcaddr }}"
        set dstaddr "{{ dstaddr }}"
        set service "{{ service }}"
        set action {{ action }}
    next
end
""",
    },
]


async def seed_config_templates(session: AsyncSession) -> int:
    created = 0
    for tpl in BUILTIN_TEMPLATES:
        result = await session.execute(
            select(ConfigTemplate).where(
                ConfigTemplate.vendor == tpl["vendor"],
                ConfigTemplate.name == tpl["name"],
            )
        )
        if result.scalar_one_or_none():
            continue
        session.add(ConfigTemplate(**tpl, is_builtin=True))
        created += 1
    return created


def render_template(template_body: str, variables: dict, schema: list | None = None) -> str:
    merged = dict(variables)
    for var in schema or []:
        name = var.get("name")
        if name and name not in merged and not var.get("required"):
            merged[name] = ""
    template = Template(template_body, undefined=StrictUndefined)
    return template.render(**merged).strip()


def validate_variables(template: ConfigTemplate, variables: dict) -> list[str]:
    errors: list[str] = []
    schema = template.variables or []
    for var in schema:
        name = var.get("name")
        if var.get("required") and not variables.get(name):
            errors.append(f"المتغير مطلوب: {var.get('label', name)}")
    return errors
