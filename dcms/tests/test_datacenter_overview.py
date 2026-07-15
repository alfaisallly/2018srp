import pytest

from app.models import DeviceType, VendorType
from app.services.datacenter_overview import infer_device_type


def test_infer_firewall_fortinet():
    assert infer_device_type(VendorType.FORTINET) == DeviceType.FIREWALL


def test_infer_switch_cisco():
    assert infer_device_type(VendorType.CISCO, "Core-SW-01") == DeviceType.SWITCH


def test_infer_router_from_name():
    assert infer_device_type(VendorType.GENERIC, "Edge-Router-01") == DeviceType.ROUTER


def test_infer_firewall_from_name():
    assert infer_device_type(VendorType.CISCO, "DC-FW-01") == DeviceType.FIREWALL
