"""Tests for VLAN discovery and the VLAN / port-VLAN sensors."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from conftest import run
from custom_components.snmp_switch import const, sensor
from custom_components.snmp_switch.coordinator import SNMPSwitchCoordinator
from custom_components.snmp_switch.snmp_client import SNMPSwitchClient

NAME = const.OID_VLAN_STATIC_NAME
EGRESS = const.OID_VLAN_STATIC_EGRESS
UNTAG = const.OID_VLAN_STATIC_UNTAGGED
PVID = const.OID_PORT_PVID
BASEMAP = const.OID_BASE_PORT_IFINDEX


def entry():
    return SimpleNamespace(entry_id="e1", data={"host": "192.0.2.1", "name": "sw"})


def make_coordinator():
    client = MagicMock()
    client.get_system_info = AsyncMock(return_value={"description": "sw"})
    client.get_interfaces = AsyncMock(return_value={1: {"name": "1"}})
    client.get_vlans = AsyncMock(return_value={"vlans": {}, "ports": {}})
    return SNMPSwitchCoordinator(MagicMock(), client, "sw", 30)


def entity_coordinator():
    coord = make_coordinator()
    coord.data = {"system": {}, "interfaces": {1: {"name": "1/1/1"}}, "vlans": {}, "port_vlans": {}}
    return coord


def vlan_client(tables):
    client = SNMPSwitchClient("192.0.2.1", 161)
    client.walk = AsyncMock(
        side_effect=lambda oid, raw_octets=False: tables.get(oid, {})
    )
    return client


# Real shape from an Aruba CX 6100: VLAN 1 = ports 1,2,13,14,15 untagged;
# VLAN 20 = ports 13-16 tagged; VLAN 40 = ports 5-12 untagged + 14,15 tagged
# (matches `show vlan` on the real switch).
REAL = {
    NAME: {f"{NAME}.1": "DEFAULT_VLAN_1", f"{NAME}.20": "Servers", f"{NAME}.40": "Cameras"},
    EGRESS: {
        f"{EGRESS}.1": "c00e",
        f"{EGRESS}.20": "000f",
        f"{EGRESS}.40": "0ff6",
    },
    UNTAG: {
        f"{UNTAG}.1": "c00e",
        f"{UNTAG}.20": "0000",
        f"{UNTAG}.40": "0ff0",
    },
    PVID: {f"{PVID}.1": "1", f"{PVID}.5": "40", f"{PVID}.16": "0"},
    BASEMAP: {f"{BASEMAP}.{i}": str(i) for i in range(1, 17)},
}


def test_get_vlans_decodes_bitmaps():
    result = run(vlan_client(REAL).get_vlans())
    v = result["vlans"]
    assert v[1]["untagged_ports"] == [1, 2, 13, 14, 15] and v[1]["tagged_ports"] == []
    assert v[20]["untagged_ports"] == [] and v[20]["tagged_ports"] == [13, 14, 15, 16]
    assert v[40]["untagged_ports"] == [5, 6, 7, 8, 9, 10, 11, 12]
    assert v[40]["tagged_ports"] == [14, 15]  # 0xf6 = ports 9-12 + 14,15
    assert v[40]["name"] == "Cameras"


def test_get_vlans_per_port_membership():
    ports = run(vlan_client(REAL).get_vlans())["ports"]
    assert ports[1] == {"pvid": 1, "untagged": [1], "tagged": []}
    assert ports[5]["pvid"] == 40 and ports[5]["untagged"] == [40]
    assert ports[13]["tagged"] == [20] and ports[13]["untagged"] == [1]
    assert ports[14]["tagged"] == [20, 40]
    assert ports[16]["pvid"] is None  # PVID 0 means unset


def test_get_vlans_maps_base_port_to_ifindex():
    tables = {
        NAME: {f"{NAME}.10": "Trusted"},
        EGRESS: {f"{EGRESS}.10": "80"},  # base port 1
        UNTAG: {f"{UNTAG}.10": "80"},
        PVID: {},
        BASEMAP: {f"{BASEMAP}.1": "1001"},
    }
    result = run(vlan_client(tables).get_vlans())
    assert result["vlans"][10]["untagged_ports"] == [1001]
    assert 1001 in result["ports"]


def test_get_vlans_empty_when_unsupported():
    assert run(vlan_client({}).get_vlans()) == {"vlans": {}, "ports": {}}


def test_get_vlans_tolerates_bad_bitmap():
    tables = {NAME: {f"{NAME}.5": "X"}, EGRESS: {f"{EGRESS}.5": "zz"}, UNTAG: {}, PVID: {}, BASEMAP: {}}
    assert run(vlan_client(tables).get_vlans())["vlans"][5]["tagged_ports"] == []


def test_vlan_failure_does_not_break_poll():
    coord = make_coordinator()
    coord.client.get_vlans = AsyncMock(side_effect=RuntimeError("boom"))
    data = run(coord._async_update_data())
    assert data["vlans"] == {} and data["port_vlans"] == {}
    assert data["interfaces"]  # rest of the poll intact


def vlan_coordinator():
    coord = entity_coordinator()
    coord.data["interfaces"] = {
        1: {"name": "1/1/1", "alias": "U7 Lite AP 1"},
        5: {"name": "1/1/5", "alias": "cam"},
        13: {"name": "1/1/13", "alias": "Z2"},
    }
    coord.data["vlans"] = {
        1: {"name": "DEFAULT_VLAN_1", "untagged_ports": [1, 13], "tagged_ports": []},
        40: {"name": "Cameras", "untagged_ports": [5], "tagged_ports": [13]},
    }
    coord.data["port_vlans"] = {
        1: {"pvid": 1, "untagged": [1], "tagged": []},
        5: {"pvid": 40, "untagged": [40], "tagged": []},
        13: {"pvid": 1, "untagged": [1], "tagged": [40]},
    }
    return coord


def test_vlan_sensors_created():
    coord = vlan_coordinator()
    added = []
    hass = SimpleNamespace(data={const.DOMAIN: {"e1": coord}})
    run(sensor.async_setup_entry(hass, entry(), added.extend))
    assert sorted(e._vlan_id for e in added if isinstance(e, sensor.SNMPVlanSensor)) == [1, 40]
    assert sorted(e._if_index for e in added if isinstance(e, sensor.SNMPPortVlanSensor)) == [1, 5, 13]


def test_no_vlan_sensors_without_data():
    coord = entity_coordinator()
    added = []
    hass = SimpleNamespace(data={const.DOMAIN: {"e1": coord}})
    run(sensor.async_setup_entry(hass, entry(), added.extend))
    assert not [e for e in added if isinstance(e, (sensor.SNMPVlanSensor, sensor.SNMPPortVlanSensor))]


def test_vlan_sensor_state_and_attributes():
    coord = vlan_coordinator()
    s = sensor.SNMPVlanSensor(coord, entry(), 40)
    assert s.native_value == "Cameras"
    attrs = s.extra_state_attributes
    assert attrs["vlan_id"] == 40
    assert attrs["untagged_ports"] == ["1/1/5"] and attrs["tagged_ports"] == ["1/1/13"]


def test_port_vlan_sensor_state_and_attributes():
    coord = vlan_coordinator()
    s = sensor.SNMPPortVlanSensor(coord, entry(), 13)
    assert s.native_value == "1 DEFAULT_VLAN_1; tagged: 40"
    attrs = s.extra_state_attributes
    assert attrs["pvid"] == 1
    assert attrs["untagged_vlans"] == ["1 DEFAULT_VLAN_1"]
    assert attrs["tagged_vlans"] == ["40 Cameras"]


def test_port_vlan_sensor_without_pvid_or_unknown_vlan():
    coord = vlan_coordinator()
    coord.data["port_vlans"][1] = {"pvid": None, "untagged": [], "tagged": []}
    coord.data["port_vlans"][5] = {"pvid": 99, "untagged": [], "tagged": []}
    assert sensor.SNMPPortVlanSensor(coord, entry(), 1).native_value == "none"
    assert sensor.SNMPPortVlanSensor(coord, entry(), 5).native_value == "99"


def test_port_vlan_state_lists_all_tagged_and_is_length_capped():
    coord = vlan_coordinator()
    coord.data["port_vlans"][13] = {"pvid": 1, "untagged": [1], "tagged": [10, 20, 30]}
    assert sensor.SNMPPortVlanSensor(coord, entry(), 13).native_value == (
        "1 DEFAULT_VLAN_1; tagged: 10, 20, 30"
    )
    coord.data["port_vlans"][13]["tagged"] = list(range(1000, 1200))
    value = sensor.SNMPPortVlanSensor(coord, entry(), 13).native_value
    assert len(value) == 255 and value.endswith("…")
