import pytest

from app.models import VendorType
from app.services.network_discovery import detect_vendor, parse_ip_range


def test_parse_cidr():
    hosts = parse_ip_range("192.168.1.0/30", None, None)
    assert hosts == ["192.168.1.1", "192.168.1.2"]


def test_parse_ip_range():
    hosts = parse_ip_range(None, "10.0.0.1", "10.0.0.3")
    assert len(hosts) == 3
    assert hosts[0] == "10.0.0.1"


def test_detect_vendor_cisco():
    vendor, model = detect_vendor("Cisco IOS Software, C2960 Software")
    assert vendor == VendorType.CISCO


def test_detect_vendor_fortinet():
    vendor, _ = detect_vendor("FortiGate-100F v7.0")
    assert vendor == VendorType.FORTINET


def test_parse_requires_input():
    with pytest.raises(ValueError):
        parse_ip_range(None, None, None)
