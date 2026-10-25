"""Tests for the PoE additions: client parsing/writes, coordinator, entities."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from conftest import UpdateFailed, run
from custom_components.snmp_switch import const, sensor, switch
from custom_components.snmp_switch.coordinator import SNMPSwitchCoordinator
from custom_components.snmp_switch.snmp_client import SNMPSwitchClient

ADMIN = const.OID_POE_PORT_ADMIN_ENABLE
DETECT = const.OID_POE_PORT_DETECTION_STATUS


def make_client(admin=None, detection=None):
    client = SNMPSwitchClient("192.0.2.1", 161)
    tables = {ADMIN: admin or {}, DETECT: detection or {}}
    client.walk = AsyncMock(side_effect=lambda oid, raw_octets=False: tables[oid])
    return client


# ── client ──────────────────────────────────────────────────────────────────

def test_get_poe_ports_parses_table():
    client = make_client(
        admin={f"{ADMIN}.1.1": "1", f"{ADMIN}.1.2": "2"},
        detection={f"{DETECT}.1.1": "3", f"{DETECT}.1.2": "1"},
    )
    assert run(client.get_poe_ports()) == {
        1: {"admin_enable": True, "detection_status": 3},
        2: {"admin_enable": False, "detection_status": 1},
    }


def test_get_poe_ports_empty_when_unsupported():
    assert run(make_client().get_poe_ports()) == {}


def test_get_poe_ports_tolerates_garbage_and_missing_detection():
    client = make_client(
        admin={f"{ADMIN}.1.1": "1", f"{ADMIN}.1.2": "N/A", f"{ADMIN}.1.3": "1"},
        detection={f"{DETECT}.1.1": "noSuchInstance"},
    )
    result = run(client.get_poe_ports())
    assert set(result) == {1, 3}  # unparsable admin row skipped
    assert result[1]["detection_status"] is None
    assert result[3]["detection_status"] is None


@pytest.mark.parametrize("enable,value", [(True, 1), (False, 2)])
def test_set_poe_port_enable_writes_expected_oid(enable, value):
    client = make_client()
    client.set_integer = AsyncMock(return_value=True)
    assert run(client.set_poe_port_enable(7, enable)) is True
    client.set_integer.assert_awaited_once_with(f"{ADMIN}.1.7", value)


def test_set_poe_port_enable_propagates_failure():
    client = make_client()
    client.set_integer = AsyncMock(return_value=False)
    assert run(client.set_poe_port_enable(7, True)) is False


# ── coordinator ─────────────────────────────────────────────────────────────

def make_coordinator(poe_result):
    client = MagicMock()
    client.get_system_info = AsyncMock(return_value={"description": "sw"})
    client.get_interfaces = AsyncMock(return_value={1: {"name": "1"}})
    if isinstance(poe_result, Exception):
        client.get_poe_ports = AsyncMock(side_effect=poe_result)
    else:
        client.get_poe_ports = AsyncMock(return_value=poe_result)
    return SNMPSwitchCoordinator(MagicMock(), client, "sw", 30)


def test_coordinator_includes_poe_data():
    coord = make_coordinator({1: {"admin_enable": True, "detection_status": 2}})
    coord.data = run(coord._async_update_data())
    assert coord.get_poe(1) == {"admin_enable": True, "detection_status": 2}
    assert coord.get_poe(99) is None


def test_poe_failure_does_not_break_poll():
    coord = make_coordinator(RuntimeError("boom"))
    data = run(coord._async_update_data())
    assert data["poe"] == {}
    assert data["interfaces"] == {1: {"name": "1"}}  # other data still present


def test_no_connection_still_raises_update_failed():
    coord = make_coordinator({})
    coord.client.get_system_info = AsyncMock(return_value={"description": None})
    with pytest.raises(UpdateFailed):
        run(coord._async_update_data())


# ── entities ────────────────────────────────────────────────────────────────

def entry():
    return SimpleNamespace(entry_id="e1", data={"host": "192.0.2.1", "name": "sw"})


def entity_coordinator(poe, write=True):
    coord = make_coordinator({})
    coord.data = {
        "system": {},
        "interfaces": {1: {"name": "1/1/1"}, 2: {"name": "1/1/2"}, 3: {"name": "1/1/3"}},
        "poe": poe,
    }
    coord.client.has_write_access = write
    coord.client.set_poe_port_enable = AsyncMock(return_value=True)
    return coord


def setup_entities(module, coord):
    added = []
    hass = SimpleNamespace(data={const.DOMAIN: {"e1": coord}})
    run(module.async_setup_entry(hass, entry(), added.extend))
    return added


def test_poe_switches_only_for_poe_ports():
    coord = entity_coordinator({1: {"admin_enable": True, "detection_status": 3}})
    poe = [e for e in setup_entities(switch, coord) if isinstance(e, switch.SNMPPoESwitch)]
    assert [e._if_index for e in poe] == [1]


def test_no_poe_entities_without_poe_data():
    coord = entity_coordinator({})
    assert not [e for e in setup_entities(switch, coord) if isinstance(e, switch.SNMPPoESwitch)]
    assert not [e for e in setup_entities(sensor, coord) if isinstance(e, sensor.SNMPPoEStatusSensor)]


def test_no_write_access_creates_no_switches():
    coord = entity_coordinator({1: {"admin_enable": True, "detection_status": 3}}, write=False)
    assert setup_entities(switch, coord) == []


def test_poe_switch_state_and_attributes():
    coord = entity_coordinator({
        1: {"admin_enable": True, "detection_status": 3},
        2: {"admin_enable": False, "detection_status": 1},
        3: {"admin_enable": True, "detection_status": 99},
    })
    s1, s2, s3 = (switch.SNMPPoESwitch(coord, entry(), i) for i in (1, 2, 3))
    assert s1.is_on is True and s2.is_on is False
    assert s1.extra_state_attributes["detection_status"] == "delivering_power"
    assert s2.extra_state_attributes["detection_status"] == "disabled"
    assert s3.extra_state_attributes["detection_status"] == "unknown"
    assert s1.icon == "mdi:flash" and s2.icon == "mdi:flash-off"


@pytest.mark.parametrize("method,enable", [("async_turn_on", True), ("async_turn_off", False)])
def test_poe_switch_actions_set_then_refresh(monkeypatch, method, enable):
    monkeypatch.setattr(switch, "POE_REFRESH_DELAY", 0)
    coord = entity_coordinator({1: {"admin_enable": not enable, "detection_status": 2}})
    run(getattr(switch.SNMPPoESwitch(coord, entry(), 1), method)())
    coord.client.set_poe_port_enable.assert_awaited_once_with(1, enable)
    assert coord.refresh_calls == 1


def test_poe_switch_skips_refresh_on_failed_write(monkeypatch):
    monkeypatch.setattr(switch, "POE_REFRESH_DELAY", 0)
    coord = entity_coordinator({1: {"admin_enable": True, "detection_status": 3}})
    coord.client.set_poe_port_enable = AsyncMock(return_value=False)
    run(switch.SNMPPoESwitch(coord, entry(), 1).async_turn_off())
    assert coord.refresh_calls == 0


@pytest.mark.parametrize("code,value,icon", [
    (1, "disabled", "mdi:flash-off"),
    (2, "searching", "mdi:flash-off"),
    (3, "delivering_power", "mdi:flash"),
    (4, "fault", "mdi:flash-off"),
    (99, "unknown", "mdi:flash-off"),
])
def test_poe_status_sensor(code, value, icon):
    coord = entity_coordinator({1: {"admin_enable": True, "detection_status": code}})
    s = sensor.SNMPPoEStatusSensor(coord, entry(), 1)
    assert s.native_value == value
    assert s.icon == icon
    assert value in s._attr_options


def test_poe_status_sensor_none_when_port_gone():
    coord = entity_coordinator({})
    assert sensor.SNMPPoEStatusSensor(coord, entry(), 1).native_value is None


def test_every_detection_status_is_a_sensor_option():
    coord = entity_coordinator({})
    options = sensor.SNMPPoEStatusSensor(coord, entry(), 1)._attr_options
    assert set(const.POE_DETECTION_STATUS_MAP.values()) <= set(options)
