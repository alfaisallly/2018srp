import asyncio

import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Device
from app.services.switch_detail import _build_port_settings, _pps_capacity_mbps, get_switch_detail


def test_pps_capacity():
    assert _pps_capacity_mbps(1000) == 1953125
    assert _pps_capacity_mbps(0) == 0


def test_port_settings_defaults():
    s = _build_port_settings(1000, "up")
    assert s["mtu"] == 1500
    assert s["max_pps"] > 0
    assert s["utilization_pct"] >= 0


async def _fetch_switch_detail():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Device).where(Device.name == "MR-Core-SW-01"))
        device = result.scalar_one_or_none()
        if not device:
            return None
        return await get_switch_detail(session, device.id)


def test_switch_detail_for_core_switch():
    detail = asyncio.run(_fetch_switch_detail())
    if detail is None:
        pytest.skip("Seed data not loaded")
    assert detail["device"]["name"] == "MR-Core-SW-01"
    assert len(detail["ports"]) >= 4
    assert detail["capacity"]["total_capacity_mbps"] > 0
    assert detail["capacity"]["min_port_mbps"] <= detail["capacity"]["max_port_mbps"]
    assert any(p.get("peer") for p in detail["ports"])
    assert len(detail["vlans"]) >= 1
    assert len(detail["insights"]) >= 1
