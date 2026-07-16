import pytest
from app.models import Permission, ROLE_PERMISSIONS, VendorType
from app.vendors import get_vendor_adapter


def test_role_permissions():
    assert Permission.MANAGE_USERS in ROLE_PERMISSIONS["admin"]
    assert Permission.MANAGE_USERS not in ROLE_PERMISSIONS["viewer"]
    assert Permission.VIEW in ROLE_PERMISSIONS["operator"]
    assert Permission.MANAGE_IPAM in ROLE_PERMISSIONS["operator"]
    assert Permission.MANAGE_INTEGRATIONS in ROLE_PERMISSIONS["operator"]


def test_vendor_adapters():
    assert get_vendor_adapter(VendorType.CISCO).vendor == "cisco"
    assert get_vendor_adapter(VendorType.JUNIPER).vendor == "juniper"
    assert get_vendor_adapter(VendorType.FORTINET).vendor == "fortinet"


def test_password_hashing():
    from app.core.security import hash_password, verify_password

    hashed = hash_password("testpass123")
    assert verify_password("testpass123", hashed)
    assert not verify_password("wrong", hashed)
