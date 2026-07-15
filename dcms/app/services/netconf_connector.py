from typing import Any

from ncclient import manager

from app.config import get_settings

settings = get_settings()


def netconf_get(
    host: str,
    username: str,
    password: str,
    filter_xml: str,
    port: int = 830,
    device_params: dict[str, Any] | None = None,
) -> str:
    params = device_params or {"name": "default"}
    with manager.connect(
        host=host,
        port=port,
        username=username,
        password=password,
        hostkey_verify=False,
        device_params=params,
        timeout=settings.ssh_timeout,
    ) as m:
        response = m.get(filter=("subtree", filter_xml))
        return str(response.data_xml)
