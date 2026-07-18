from app.models import Device, VendorType
from app.services.network_snmp_sync import NETWORK_SEGMENTS, get_network_segment, is_snmp_inventory_eligible
from app.services.snmp_inventory import (
    build_inventory,
    parse_cdp_neighbors,
    parse_if_table,
)


def test_network_segments_defined():
    assert "transport_branch" in NETWORK_SEGMENTS
    assert "internal" in NETWORK_SEGMENTS


def test_snmp_eligible_transport_only():
    transport = Device(
        id=1,
        datacenter_id=1,
        name="RTR-01",
        hostname="rtr",
        ip_address="10.0.0.1",
        vendor=VendorType.CISCO,
        tags={"network_segment": "transport_branch"},
    )
    internal = Device(
        id=2,
        datacenter_id=1,
        name="SW-01",
        hostname="sw",
        ip_address="10.0.0.2",
        vendor=VendorType.CISCO,
        tags={"network_segment": "internal", "snmp_inventory": False},
    )
    assert is_snmp_inventory_eligible(transport)
    assert not is_snmp_inventory_eligible(internal)
    assert get_network_segment(transport) == "transport_branch"


def test_parse_if_table_and_neighbors():
    walk = {
        "1.3.6.1.2.1.2.2.1.2.10": "GigabitEthernet1/0/1",
        "1.3.6.1.2.1.2.2.1.3.10": "6",
        "1.3.6.1.2.1.2.2.1.5.10": "10000000000",
        "1.3.6.1.2.1.2.2.1.7.10": "1",
        "1.3.6.1.2.1.2.2.1.8.10": "1",
        "1.3.6.1.4.1.9.9.23.1.2.1.1.6.10.1": "CORE-SW-02",
        "1.3.6.1.4.1.9.9.23.1.2.1.1.7.10.1": "Gi1/0/24",
    }
    if_rows = parse_if_table(walk)
    neighbors = parse_cdp_neighbors(walk)
    inv = build_inventory(if_rows, neighbors, [], {})
    assert len(inv.interfaces) == 1
    assert inv.interfaces[0].name == "GigabitEthernet1/0/1"
    assert inv.interfaces[0].oper_status == "up"
    assert inv.interfaces[0].speed_mbps == 10000
    assert inv.interfaces[0].neighbor_hostname == "CORE-SW-02"
