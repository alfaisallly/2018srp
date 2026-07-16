"""Sync external integrations (PRTG, VMware) and store status."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IntegrationEndpoint, IntegrationType
from app.services.prtg_client import sync_prtg_sensor_summary, test_prtg_connection
from app.services.vmware_client import collect_vmware_metrics, vmware_login


async def sync_integration(session: AsyncSession, endpoint_id: int) -> dict:
    result = await session.execute(select(IntegrationEndpoint).where(IntegrationEndpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise ValueError("Integration not found")
    if not endpoint.enabled:
        raise ValueError("Integration is disabled")

    now = datetime.now(timezone.utc)
    try:
        if endpoint.integration_type == IntegrationType.PRTG:
            if not endpoint.api_token:
                raise ValueError("PRTG API token required")
            summary = await sync_prtg_sensor_summary(endpoint.base_url, endpoint.api_token)
            endpoint.last_sync_status = "ok"
            endpoint.last_sync_at = now
            extra = dict(endpoint.extra or {})
            extra["prtg_summary"] = summary
            endpoint.extra = extra
            await session.flush()
            return {"ok": True, "type": "prtg", "summary": summary}

        if endpoint.integration_type == IntegrationType.VMWARE:
            host = endpoint.base_url.replace("https://", "").replace("http://", "").split("/")[0]
            port = int((endpoint.extra or {}).get("port", 443))
            password = endpoint.api_token or ""
            token = None
            if endpoint.username and password:
                token = await vmware_login(host, endpoint.username, password, port)
            metrics = await collect_vmware_metrics(
                host,
                endpoint.username or "",
                password,
                token=token,
                port=port,
            )
            endpoint.last_sync_status = "ok"
            endpoint.last_sync_at = now
            extra = dict(endpoint.extra or {})
            extra["vmware_metrics"] = {name: value for name, value, _ in metrics}
            endpoint.extra = extra
            await session.flush()
            return {"ok": True, "type": "vmware", "metrics": extra["vmware_metrics"]}

        raise ValueError(f"Unsupported integration type: {endpoint.integration_type}")
    except Exception as exc:
        endpoint.last_sync_status = f"error: {exc}"
        endpoint.last_sync_at = now
        await session.flush()
        raise


async def test_integration(session: AsyncSession, endpoint_id: int) -> dict:
    result = await session.execute(select(IntegrationEndpoint).where(IntegrationEndpoint.id == endpoint_id))
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise ValueError("Integration not found")

    if endpoint.integration_type == IntegrationType.PRTG:
        if not endpoint.api_token:
            return {"ok": False, "message": "PRTG API token required"}
        return await test_prtg_connection(endpoint.base_url, endpoint.api_token)

    if endpoint.integration_type == IntegrationType.VMWARE:
        host = endpoint.base_url.replace("https://", "").replace("http://", "").split("/")[0]
        port = (endpoint.extra or {}).get("port", 443)
        try:
            if endpoint.username and endpoint.api_token:
                await vmware_login(host, endpoint.username, endpoint.api_token, port)
                return {"ok": True, "message": "VMware session established"}
            return {"ok": False, "message": "VMware username and password/token required"}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    return {"ok": False, "message": "Unknown integration type"}


async def sync_all_integrations(session: AsyncSession) -> dict:
    result = await session.execute(select(IntegrationEndpoint).where(IntegrationEndpoint.enabled.is_(True)))
    endpoints = list(result.scalars().all())
    ok, failed = 0, 0
    errors: list[str] = []
    for ep in endpoints:
        try:
            await sync_integration(session, ep.id)
            ok += 1
        except Exception as exc:
            failed += 1
            errors.append(f"{ep.name}: {exc}")
    return {"total": len(endpoints), "success": ok, "failed": failed, "errors": errors[:20]}
