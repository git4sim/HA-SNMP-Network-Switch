"""Virtual interfaces (VLAN SVIs, loopbacks...) must not be treated as ports."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from conftest import run
from custom_components.snmp_switch import const, sensor
from custom_components.snmp_switch.coordinator import SNMPSwitchCoordinator
from custom_components.snmp_switch.snmp_client import SNMPSwitchClient


def make_client(types: dict[int, int], extra: dict[str, dict] | None = None):
    """Client whose walks return a minimal ifTable with the given ifTypes."""
    descr = {f"{const.OID_IF_DESCR}.{i}": f"if{i}" for i in types}
    tables = {
        const.OID_IF_DESCR: descr,
        const.OID_IF_TYPE: {f"{const.OID_IF_TYPE}.{i}": str(t) for i, t in types.items()},
        const.OID_IF_ADMIN_STATUS: {f"{const.OID_IF_ADMIN_STATUS}.{i}": "1" for i in types},
        const.OID_IF_OPER_STATUS: {f"{const.OID_IF_OPER_STATUS}.{i}": "1" for i in types},
    }
    tables.update(extra or {})
    client = SNMPSwitchClient("192.0.2.1", 161)
    client.walk = AsyncMock(side_effect=lambda oid, raw_octets=False: tables.get(oid, {}))
    return client


def test_physical_ports_are_kept():
    # 6 = ethernetCsmacd, 117 = gigabitEthernet, 161 = ieee8023adLag
    result = run(make_client({1: 6, 2: 117, 3: 161}).get_interfaces())
    assert sorted(result) == [1, 2, 3]


@pytest.mark.parametrize("virtual_type", sorted(const.VIRTUAL_IF_TYPES))
def test_virtual_interfaces_are_dropped(virtual_type):
    # Aruba CX reports its management SVI as ifIndex 16777217, type 53.
    result = run(make_client({1: 6, 16777217: virtual_type}).get_interfaces())
    assert sorted(result) == [1]


def test_interface_without_type_is_kept():
    # If a device doesn't answer ifType, don't lose its ports.
    client = make_client({1: 6, 2: 6})
    client.walk = AsyncMock(side_effect=lambda oid, raw_octets=False: {
        const.OID_IF_DESCR: {f"{const.OID_IF_DESCR}.1": "a", f"{const.OID_IF_DESCR}.2": "b"},
    }.get(oid, {}))
    assert sorted(run(client.get_interfaces())) == [1, 2]


def test_unparsable_type_keeps_interface():
    client = make_client({1: 6})
    client.walk = AsyncMock(side_effect=lambda oid, raw_octets=False: {
        const.OID_IF_DESCR: {f"{const.OID_IF_DESCR}.1": "a"},
        const.OID_IF_TYPE: {f"{const.OID_IF_TYPE}.1": "weird"},
    }.get(oid, {}))
    assert sorted(run(client.get_interfaces())) == [1]


def test_port_count_sensor_counts_ports_not_ifnumber():
    # Switch reports ifNumber=17 (16 ports + 1 VLAN SVI); only 16 are ports.
    coord = SNMPSwitchCoordinator(MagicMock(), MagicMock(), "sw", 30)
    coord.data = {
        "system": {"if_number": "17"},
        "interfaces": {i: {} for i in range(1, 17)},
    }
    entry = SimpleNamespace(entry_id="e1", data={"host": "192.0.2.1", "name": "sw"})
    assert sensor.SNMPPortCountSensor(coord, entry).native_value == 16


def test_port_count_falls_back_to_ifnumber_without_interface_data():
    coord = SNMPSwitchCoordinator(MagicMock(), MagicMock(), "sw", 30)
    coord.data = {"system": {"if_number": "17"}}
    entry = SimpleNamespace(entry_id="e1", data={"host": "192.0.2.1", "name": "sw"})
    assert sensor.SNMPPortCountSensor(coord, entry).native_value == 17


def test_port_count_falls_back_to_ifnumber_when_interface_walk_is_empty():
    coord = SNMPSwitchCoordinator(MagicMock(), MagicMock(), "sw", 30)
    coord.data = {"system": {"if_number": "17"}, "interfaces": {}}
    entry = SimpleNamespace(entry_id="e1", data={"host": "192.0.2.1", "name": "sw"})
    assert sensor.SNMPPortCountSensor(coord, entry).native_value == 17
