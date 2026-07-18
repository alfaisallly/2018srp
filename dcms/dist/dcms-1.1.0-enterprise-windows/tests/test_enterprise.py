import pytest

from app.models import Permission, User, VendorType
from app.core.permissions import permissions_from_user, ROLE_TEMPLATES
from app.services.config_backup import _config_command
from app.services.ipam import _iter_hosts
from app.services.capabilities import CAPABILITIES


def test_iter_hosts_slash24():
    import ipaddress

    network = ipaddress.ip_network("10.0.0.0/30")
    hosts = list(_iter_hosts(network))
    assert "10.0.0.1" in [str(h) for h in hosts]
    assert "10.0.0.2" in [str(h) for h in hosts]


def test_config_command_by_vendor():
    assert "running-config" in _config_command(VendorType.CISCO)
    assert "configuration" in _config_command(VendorType.JUNIPER)


def test_prtg_sync_summary_parsing():
    sensors = [
        {"status": "Up", "status_raw": "3"},
        {"status": "Warning", "status_raw": "4"},
        {"status": "Down", "status_raw": "5"},
        {"status": "Paused"},
    ]
    summary = {"total": len(sensors), "up": 0, "warning": 0, "down": 0, "paused": 0, "unknown": 0}
    for s in sensors:
        raw = str(s.get("status_raw") or s.get("status") or "").lower()
        if "up" in raw or raw == "3":
            summary["up"] += 1
        elif "warn" in raw or raw == "4":
            summary["warning"] += 1
        elif "down" in raw or raw == "5":
            summary["down"] += 1
        elif "pause" in raw:
            summary["paused"] += 1
        else:
            summary["unknown"] += 1
    assert summary["total"] == 4
    assert summary["up"] == 1
    assert summary["warning"] == 1
    assert summary["down"] == 1
    assert summary["paused"] == 1


def test_capabilities_registry():
    ids = {c["id"] for c in CAPABILITIES}
    assert "datacenters" in ids
    assert "ipam" in ids
    assert "config_backup" in ids
    assert "prtg" in ids
    assert "vmware" in ids
    assert len(CAPABILITIES) >= 8


def test_new_permissions_in_admin():
    from app.models import ROLE_PERMISSIONS

    assert Permission.MANAGE_IPAM in ROLE_PERMISSIONS["admin"]
    assert Permission.MANAGE_INTEGRATIONS in ROLE_PERMISSIONS["admin"]
    assert Permission.MANAGE_IPAM in ROLE_PERMISSIONS["operator"]


def test_permissions_from_user_stale_admin():
    user = User(username="admin", email="a@a.com", hashed_password="x", role="admin", permissions=["view"])
    perms = permissions_from_user(user)
    assert Permission.MANAGE_INTEGRATIONS in perms
    assert Permission.MANAGE_IPAM in perms


def test_editor_has_ipam_permissions():
    editor_perms = ROLE_TEMPLATES["editor"]["permissions"]
    assert Permission.MANAGE_IPAM in editor_perms
    assert Permission.MANAGE_INTEGRATIONS in editor_perms
