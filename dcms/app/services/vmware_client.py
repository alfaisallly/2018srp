"""VMware vSphere / ESXi REST metrics collection."""

from typing import Any

import httpx


async def _vmware_get(
    host: str, path: str, session_token: str, port: int = 443, verify_ssl: bool = False
) -> dict[str, Any]:
    url = f"https://{host}:{port}{path}"
    headers = {"vmware-api-session-id": session_token, "Accept": "application/json"}
    async with httpx.AsyncClient(verify=verify_ssl, timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        if response.content:
            return response.json()
        return {}


async def vmware_login(host: str, username: str, password: str, port: int = 443) -> str:
    url = f"https://{host}:{port}/rest/com/vmware/cis/session"
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        response = await client.post(url, auth=(username, password))
        response.raise_for_status()
        data = response.json()
        token = data.get("value") if isinstance(data, dict) else None
        if not token:
            raise ValueError("VMware session token not returned")
        return token


async def collect_vmware_metrics(
    host: str, username: str, password: str, token: str | None = None, port: int = 443
) -> list[tuple[str, float, str | None]]:
    """Collect host CPU, memory, VM count, and datastore usage where available."""
    metrics: list[tuple[str, float, str | None]] = []
    session_token = token
    if not session_token and username and password:
        try:
            session_token = await vmware_login(host, username, password, port)
        except Exception:
            session_token = None

    if not session_token:
        from app.services.rest_api_connector import rest_get

        try:
            data = await rest_get(host, "/rest/appliance/system/version", token or "", port, verify_ssl=False)
            version = data.get("version", "unknown") if isinstance(data, dict) else "unknown"
            metrics.append(("reachable", 1.0, "bool"))
            metrics.append(("esxi_version_info", float(len(version)), "chars"))
            return metrics
        except Exception:
            return [("reachable", 0.0, "bool")]

    metrics.append(("reachable", 1.0, "bool"))

    try:
        hosts_data = await _vmware_get(host, "/rest/vcenter/host", session_token, port)
        host_list = hosts_data.get("value", []) if isinstance(hosts_data, dict) else []
        metrics.append(("host_count", float(len(host_list)), "count"))
    except Exception:
        host_list = []

    try:
        vms_data = await _vmware_get(host, "/rest/vcenter/vm", session_token, port)
        vm_list = vms_data.get("value", []) if isinstance(vms_data, dict) else []
        metrics.append(("vm_count", float(len(vm_list)), "count"))
    except Exception:
        pass

    try:
        ds_data = await _vmware_get(host, "/rest/vcenter/datastore", session_token, port)
        ds_list = ds_data.get("value", []) if isinstance(ds_data, dict) else []
        metrics.append(("datastore_count", float(len(ds_list)), "count"))
    except Exception:
        pass

    if host_list:
        host_id = host_list[0].get("host") if isinstance(host_list[0], dict) else None
        if host_id:
            try:
                hw = await _vmware_get(host, f"/rest/vcenter/host/{host_id}", session_token, port)
                if isinstance(hw, dict) and hw.get("value"):
                    metrics.append(("host_online", 1.0, "bool"))
            except Exception:
                pass

    return metrics
