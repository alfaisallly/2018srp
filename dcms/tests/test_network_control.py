"""Tests for network control module."""

import pytest

from app.models import VendorType
from app.services.config_templates import BUILTIN_TEMPLATES, render_template, validate_variables


def test_builtin_templates_count():
    assert len(BUILTIN_TEMPLATES) >= 10
    vendors = {t["vendor"] for t in BUILTIN_TEMPLATES}
    assert VendorType.CISCO in vendors
    assert VendorType.JUNIPER in vendors
    assert VendorType.FORTINET in vendors


def test_cisco_vlan_template_render():
    tpl = next(t for t in BUILTIN_TEMPLATES if t["name"] == "cisco_vlan_create")
    output = render_template(tpl["template_body"], {"vlan_id": 100, "vlan_name": "Management"})
    assert "vlan 100" in output
    assert "name Management" in output


def test_juniper_vlan_template_render():
    tpl = next(t for t in BUILTIN_TEMPLATES if t["name"] == "juniper_vlan_create")
    output = render_template(tpl["template_body"], {"vlan_name": "DATA", "vlan_id": 50}, tpl["variables"])
    assert "vlan-id 50" in output
    assert "vlans DATA" in output


def test_backup_wireless_templates_exist():
    cisco_backup = [t for t in BUILTIN_TEMPLATES if t["category"] == "backup_link"]
    assert len(cisco_backup) >= 2
    names = {t["name"] for t in cisco_backup}
    assert "cisco_backup_wireless_link" in names
    assert "juniper_backup_wireless" in names


def test_validate_variables_required():
    tpl_data = BUILTIN_TEMPLATES[0]
    from app.models import ConfigTemplate

    template = ConfigTemplate(**tpl_data)
    errors = validate_variables(template, {})
    assert len(errors) >= 1


def test_topology_link_labels():
    from app.services.topology_builder import LINK_COLORS, LINK_LABELS
    from app.models import LinkType

    assert LinkType.FIBER in LINK_COLORS
    assert LINK_LABELS[LinkType.WIRELESS] == "لاسلكي"
