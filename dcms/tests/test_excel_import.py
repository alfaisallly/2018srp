import pytest

from app.services.excel_import import (
    build_topology,
    generate_template_bytes,
    parse_excel_bytes,
    ParsedAsset,
    ParsedLink,
)


def test_generate_template_and_parse():
    content = generate_template_bytes()
    assert content[:2] == b"PK"
    result = parse_excel_bytes(content)
    assert result.summary["total"] >= 3
    assert result.summary["devices"] >= 1
    assert result.summary["servers"] >= 1
    assert result.summary["storage"] >= 1
    assert "DC-MOROOR-01" in result.datacenters
    assert result.summary["links"] >= 2


def test_parse_assets_types():
    content = generate_template_bytes()
    result = parse_excel_bytes(content)
    types = {a.asset_type for a in result.assets}
    assert "device" in types
    assert "server" in types
    assert "storage" in types


def test_build_topology_with_links():
    assets = [
        ParsedAsset("DC-1", "device", "SW-01", "sw-01", "10.0.0.1", row=2),
        ParsedAsset("DC-1", "server", "SRV-01", "srv-01", "10.0.0.2", row=3),
    ]
    links = [ParsedLink("DC-1", "SW-01", "SRV-01", "uplink", row=2)]
    ids = {"SW-01": "dev-1", "SRV-01": "srv-1", "10.0.0.1": "dev-1", "10.0.0.2": "srv-1"}
    topo = build_topology(assets, links, "DC-1", ids)
    assert len(topo["nodes"]) >= 2
    assert len(topo["edges"]) >= 1
    assert any(e.get("from") == "dev-1" for e in topo["edges"])


def test_parse_empty_bytes():
    with pytest.raises(Exception):
        parse_excel_bytes(b"not-excel")
