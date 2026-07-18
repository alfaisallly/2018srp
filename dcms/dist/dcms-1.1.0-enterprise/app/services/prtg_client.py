"""Paessler PRTG Network Monitor API client."""

from typing import Any

import httpx


async def prtg_request(base_url: str, api_token: str, endpoint: str, params: dict | None = None) -> Any:
    """Call PRTG JSON API (passhash token auth)."""
    base = base_url.rstrip("/")
    url = f"{base}{endpoint}"
    query = {"apitoken": api_token, **(params or {})}
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        response = await client.get(url, params=query)
        response.raise_for_status()
        return response.json()


async def fetch_prtg_sensors(base_url: str, api_token: str, limit: int = 500) -> list[dict]:
    data = await prtg_request(
        base_url,
        api_token,
        "/api/table.json",
        {"content": "sensors", "columns": "objid,sensor,device,status,message,lastvalue", "count": str(limit)},
    )
    if isinstance(data, dict):
        return data.get("sensors") or data.get("prtg") or []
    return []


async def test_prtg_connection(base_url: str, api_token: str) -> dict:
    try:
        data = await prtg_request(base_url, api_token, "/api/getstatus.json")
        version = data.get("Version", "unknown") if isinstance(data, dict) else "unknown"
        return {"ok": True, "version": version, "message": "Connected to PRTG"}
    except Exception as exc:
        return {"ok": False, "version": None, "message": str(exc)}


async def sync_prtg_sensor_summary(base_url: str, api_token: str) -> dict:
    """Pull sensor status counts from PRTG for dashboard integration."""
    sensors = await fetch_prtg_sensors(base_url, api_token)
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
    return summary
