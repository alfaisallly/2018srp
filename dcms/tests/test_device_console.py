"""Tests for device console and command library."""

from app.models import VendorType
from app.services.command_library import list_commands
from app.services.device_console import wrap_config_push


def test_command_library_vendors():
    cisco = list_commands(VendorType.CISCO)
    juniper = list_commands(VendorType.JUNIPER)
    palo = list_commands(VendorType.PALO_ALTO)
    assert len(cisco) >= 5
    assert len(juniper) >= 5
    assert len(palo) >= 5
    assert all(c["vendor"] == "cisco" for c in cisco)
    assert all(c["vendor"] == "palo_alto" for c in palo)


def test_wrap_cisco_config():
    wrapped = wrap_config_push(VendorType.CISCO, "vlan 10\n name TEST")
    assert wrapped.startswith("configure terminal")
    assert "vlan 10" in wrapped
    assert wrapped.endswith("end")


def test_wrap_juniper_set_commands():
    wrapped = wrap_config_push(VendorType.JUNIPER, "set vlans DATA vlan-id 10")
    assert "configure private" in wrapped
    assert "commit and-quit" in wrapped


def test_wrap_palo_alto_config():
    wrapped = wrap_config_push(VendorType.PALO_ALTO, "set deviceconfig system hostname PA-FW-01")
    assert wrapped.startswith("configure")
    assert "commit" in wrapped


def test_palo_alto_templates_exist():
    from app.services.config_templates import BUILTIN_TEMPLATES

    palo = [t for t in BUILTIN_TEMPLATES if t["vendor"] == VendorType.PALO_ALTO]
    assert len(palo) >= 3
