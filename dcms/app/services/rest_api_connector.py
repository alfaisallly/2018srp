from typing import Any

import httpx


async def rest_get(
    host: str,
    path: str,
    token: str,
    port: int = 443,
    verify_ssl: bool = True,
    auth_style: str = "bearer",
) -> dict[str, Any]:
    url = f"https://{host}:{port}{path}"
    if auth_style == "api-token":
        headers = {"api-token": token, "Accept": "application/json"}
    else:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(verify=verify_ssl, timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
