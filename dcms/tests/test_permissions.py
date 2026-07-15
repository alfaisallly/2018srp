from app.core.permissions import ROLE_TEMPLATES, permissions_from_user, resolve_permissions
from app.models import Permission, User


def test_resolve_viewer():
    perms = resolve_permissions("viewer")
    assert "view" in perms
    assert "manage_users" not in perms


def test_resolve_editor():
    perms = resolve_permissions("editor")
    assert "manage_devices" in perms
    assert "manage_users" not in perms


def test_resolve_custom():
    perms = resolve_permissions("custom", ["view", "manage_alerts"])
    assert perms == ["view", "manage_alerts"]


def test_permissions_from_user_with_custom():
    user = User(username="test", email="t@t.com", hashed_password="x", role="viewer", permissions=["view", "manage_storage"])
    perms = permissions_from_user(user)
    assert Permission.MANAGE_STORAGE in perms
    assert Permission.MANAGE_USERS not in perms


def test_role_templates_exist():
    assert "viewer" in ROLE_TEMPLATES
    assert "editor" in ROLE_TEMPLATES
    assert "admin" in ROLE_TEMPLATES
