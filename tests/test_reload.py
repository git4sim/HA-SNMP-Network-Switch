"""Changing options must reload the entry through Home Assistant."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from conftest import run
from custom_components import snmp_switch


def test_options_change_reloads_via_config_entries():
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_reload=AsyncMock()))
    entry = SimpleNamespace(entry_id="abc123")
    run(snmp_switch._async_reload_entry(hass, entry))
    hass.config_entries.async_reload.assert_awaited_once_with("abc123")


def test_reload_does_not_call_setup_directly(monkeypatch):
    # Calling async_setup_entry by hand is what broke the coordinator's
    # first refresh (no config-entry context).
    called = []
    monkeypatch.setattr(snmp_switch, "async_setup_entry", AsyncMock(side_effect=lambda *a: called.append(a)))
    monkeypatch.setattr(snmp_switch, "async_unload_entry", AsyncMock(side_effect=lambda *a: called.append(a)))
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_reload=AsyncMock()))
    run(snmp_switch._async_reload_entry(hass, SimpleNamespace(entry_id="x")))
    assert called == []
