from app.models import Permission, ROLE_PERMISSIONS, ServerOSType, StorageVendor


def test_server_permissions():
    assert Permission.MANAGE_SERVERS in ROLE_PERMISSIONS["admin"]
    assert Permission.MANAGE_SERVERS in ROLE_PERMISSIONS["operator"]
    assert Permission.MANAGE_STORAGE in ROLE_PERMISSIONS["operator"]


def test_server_os_types():
    assert ServerOSType.LINUX.value == "linux"
    assert StorageVendor.NETAPP.value == "netapp"
