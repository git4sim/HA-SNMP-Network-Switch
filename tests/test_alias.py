"""Port names from the switch config (ifAlias): attribute + opt-in Description."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.snmp_switch import const, sensor
from custom_components.snmp_switch.coordinator import SNMPSwitchCoordinator


def make_entry(**options):
    return SimpleNamespace(
        entry_id="e1", data={"host": "192.0.2.1", "name": "sw"}, options=options
    )


def make_coordinator(interfaces):
    coord = SNMPSwitchCoordinator(MagicMock(), MagicMock(), "sw", 30)
    coord.data = {"system": {}, "interfaces": interfaces}
    return coord


IFACES = {
    1: {"name": "1/1/1", "description": "1/1/1", "alias": "U7 Lite AP 1"},
    2: {"name": "1/1/2", "description": "1/1/2", "alias": ""},
}


def test_option_constant_name():
    assert const.CONF_USE_PORT_NAMES == "use_port_names"


def test_description_defaults_to_hardware_name():
    # Unchanged behaviour when the option is not set.
    s = sensor.SNMPPortDescriptionSensor(make_coordinator(IFACES), make_entry(), 1)
    assert s.native_value == "1/1/1"


@pytest.mark.parametrize("flag", [False, None])
def test_description_ignores_alias_when_option_off(flag):
    entry = make_entry(**({} if flag is None else {const.CONF_USE_PORT_NAMES: flag}))
    s = sensor.SNMPPortDescriptionSensor(make_coordinator(IFACES), entry, 1)
    assert s.native_value == "1/1/1"


def test_description_shows_alias_when_option_on():
    entry = make_entry(**{const.CONF_USE_PORT_NAMES: True})
    s = sensor.SNMPPortDescriptionSensor(make_coordinator(IFACES), entry, 1)
    assert s.native_value == "U7 Lite AP 1"


def test_description_falls_back_when_alias_empty():
    entry = make_entry(**{const.CONF_USE_PORT_NAMES: True})
    s = sensor.SNMPPortDescriptionSensor(make_coordinator(IFACES), entry, 2)
    assert s.native_value == "1/1/2"


def test_option_read_from_entry_data_too():
    # Options flow results live in entry.options, but data is also honoured
    # (the integration merges the two everywhere else).
    entry = SimpleNamespace(
        entry_id="e1",
        data={"host": "h", "name": "sw", const.CONF_USE_PORT_NAMES: True},
        options={},
    )
    s = sensor.SNMPPortDescriptionSensor(make_coordinator(IFACES), entry, 1)
    assert s.native_value == "U7 Lite AP 1"


@pytest.mark.parametrize("cls", [
    sensor.SNMPPortAdminStatusSensor,
    sensor.SNMPPortSpeedSensor,
    sensor.SNMPPortMacSensor,
])
def test_port_sensors_expose_alias_attribute(cls):
    s = cls(make_coordinator(IFACES), make_entry(), 1)
    assert s.extra_state_attributes == {"alias": "U7 Lite AP 1"}


def test_alias_attribute_empty_when_port_missing():
    s = sensor.SNMPPortAdminStatusSensor(make_coordinator({}), make_entry(), 9)
    assert s.extra_state_attributes is None


def test_system_sensors_have_no_alias_attribute():
    s = sensor.SNMPSystemSensor(make_coordinator(IFACES), make_entry(), "name", "sys_name", "mdi:tag")
    assert s.extra_state_attributes is None
