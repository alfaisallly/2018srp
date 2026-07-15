from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
)

from app.config import get_settings

settings = get_settings()


async def _async_snmp_get(host: str, community: str, oid: str, port: int) -> str | None:
    snmp_engine = SnmpEngine()
    transport = await UdpTransportTarget.create((host, port), timeout=settings.snmp_timeout)
    error_indication, _, _, var_binds = await get_cmd(
        snmp_engine,
        CommunityData(community, mpModel=1),
        transport,
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )
    snmp_engine.close_dispatcher()
    if error_indication:
        return None
    for var_bind in var_binds:
        return str(var_bind[1])
    return None


def snmp_get_bulk(host: str, community: str, oids: dict[str, str], port: int = 161) -> dict[str, str]:
    """Sync wrapper for SNMP GET used in thread pool."""
    import asyncio

    async def _run() -> dict[str, str]:
        results: dict[str, str] = {}
        for name, oid in oids.items():
            value = await _async_snmp_get(host, community, oid, port)
            if value is not None:
                results[name] = value
        return results

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _run())
                return future.result(timeout=settings.snmp_timeout + 5)
        return loop.run_until_complete(_run())
    except RuntimeError:
        return asyncio.run(_run())
