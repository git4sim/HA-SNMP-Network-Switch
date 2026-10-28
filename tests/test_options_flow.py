"""Options flow: settings and credentials are separate steps."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from conftest import run


# config_flow subclasses ConfigFlow with a `domain=` class keyword, which the
# shared permissive dummy base can't take, so give it plain stand-ins.
class _ConfigFlow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()


class _OptionsFlow:
    pass


_config_entries = sys.modules["homeassistant.config_entries"]
_config_entries.ConfigFlow = _ConfigFlow
_config_entries.OptionsFlow = _OptionsFlow
# `from homeassistant import config_entries` must resolve to this module.
sys.modules["homeassistant"].config_entries = _config_entries

from custom_components.snmp_switch import config_flow  # noqa: E402


def make_flow(data=None, options=None):
    flow = config_flow.SNMPSwitchOptionsFlow()
    flow.config_entry = SimpleNamespace(data=data or {}, options=options or {})
    # Capture what the flow returns instead of needing Home Assistant's machinery.
    flow.async_show_menu = lambda **kw: ("menu", kw)
    flow.async_show_form = lambda **kw: ("form", kw)
    flow.async_create_entry = lambda **kw: ("entry", kw)
    return flow


def schema_keys(form_kwargs):
    schema = form_kwargs["data_schema"]
    return {marker.args[0] for marker in schema.args[0]}


V2C = {"snmp_version": "2c", "host": "h", "community_read": "public"}
V3 = {
    "snmp_version": "3", "host": "h", "v3_username": "hass",
    "v3_auth_protocol": "SHA", "v3_auth_key": "authsecret1",
    "v3_priv_protocol": "AES-128", "v3_priv_key": "privsecret1",
}


def test_init_is_a_menu():
    kind, kw = run(make_flow(V2C).async_step_init())
    assert kind == "menu" and kw["menu_options"] == ["settings", "credentials"]


@pytest.mark.parametrize("data", [V2C, V3])
def test_settings_form_has_no_credential_fields(data):
    kind, kw = run(make_flow(data).async_step_settings())
    keys = schema_keys(kw)
    assert kind == "form" and kw["step_id"] == "settings"
    assert {"scan_interval", "port", "name"} <= keys
    assert not keys & {
        "community_read", "community_write", "v3_username", "v3_auth_key", "v3_priv_key",
    }


def test_saving_settings_keeps_existing_credential_options():
    flow = make_flow(V3, options={"v3_auth_key": "changed-earlier", "scan_interval": 60})
    kind, kw = run(flow.async_step_settings({"name": "Core switch", "scan_interval": 30}))
    assert kind == "entry"
    assert kw["data"]["v3_auth_key"] == "changed-earlier"  # untouched
    assert kw["data"]["scan_interval"] == 30 and kw["data"]["name"] == "Core switch"


def test_credentials_form_v2c_and_v3_fields():
    _, kw = run(make_flow(V2C).async_step_credentials())
    assert schema_keys(kw) == {"community_read", "community_write"}
    _, kw = run(make_flow(V3).async_step_credentials())
    assert "v3_username" in schema_keys(kw) and "scan_interval" not in schema_keys(kw)


def test_saving_credentials_keeps_settings_options():
    flow = make_flow(V2C, options={"name": "Core switch", "scan_interval": 45})
    kind, kw = run(flow.async_step_credentials({"community_read": "newpub", "community_write": ""}))
    assert kind == "entry"
    assert kw["data"]["name"] == "Core switch" and kw["data"]["scan_interval"] == 45
    assert kw["data"]["community_read"] == "newpub"
    assert kw["data"]["community_write"] is None  # empty write community clears it


def test_v3_priv_without_auth_is_rejected():
    flow = make_flow(V3)
    kind, kw = run(flow.async_step_credentials({
        "v3_username": "hass", "v3_auth_protocol": "none", "v3_auth_key": "",
        "v3_priv_protocol": "AES-128", "v3_priv_key": "privsecret1",
    }))
    assert kind == "form" and kw["errors"] == {"v3_auth_key": "priv_requires_auth"}
