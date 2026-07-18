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


async def _async_snmp_walk(
    host: str,
    community: str,
    oid_prefix: str,
    port: int,
    max_rows: int = 512,
) -> dict[str, str]:
    from pysnmp.hlapi.v3arch.asyncio import next_cmd

    results: dict[str, str] = {}
    snmp_engine = SnmpEngine()
    transport = await UdpTransportTarget.create((host, port), timeout=settings.snmp_timeout)
    var_binds = ObjectType(ObjectIdentity(oid_prefix))

    for _ in range(max_rows):
        error_indication, _error_status, _error_index, var_bind_table = await next_cmd(
            snmp_engine,
            CommunityData(community, mpModel=1),
            transport,
            ContextData(),
            var_binds,
        )
        if error_indication:
            break
        if not var_bind_table:
            break
        finished = True
        for oid, value in var_bind_table:
            oid_str = str(oid)
            if not oid_str.startswith(oid_prefix):
                snmp_engine.close_dispatcher()
                return results
            results[oid_str] = str(value)
            var_binds = ObjectType(ObjectIdentity(oid_str))
            finished = False
        if finished:
            break
    snmp_engine.close_dispatcher()
    return results


def snmp_walk(host: str, community: str, oid_prefix: str, port: int = 161, max_rows: int = 512) -> dict[str, str]:
    """Sync wrapper for SNMP WALK used in thread pool."""
    import asyncio

    async def _run() -> dict[str, str]:
        return await _async_snmp_walk(host, community, oid_prefix, port, max_rows)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _run())
                return future.result(timeout=settings.snmp_timeout * 30)
        return loop.run_until_complete(_run())
    except RuntimeError:
        return asyncio.run(_run())


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
