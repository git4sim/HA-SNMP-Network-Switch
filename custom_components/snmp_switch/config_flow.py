"""Config Flow for SNMP Network Switch."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback

# snmp_client intentionally NOT imported at module level —
# pysnmp is installed as a requirement AFTER this module is first loaded by HA.
# A top-level import here (or anywhere in the package init chain) causes an
# ImportError that HA surfaces as "Invalid handler specified".
from .const import (
    CONF_COMMUNITY_READ,
    CONF_COMMUNITY_WRITE,
    CONF_SCAN_INTERVAL,
    CONF_SNMP_VERSION,
    CONF_V3_AUTH_KEY,
    CONF_V3_AUTH_PROTOCOL,
    CONF_V3_CONTEXT_NAME,
    CONF_V3_PRIV_KEY,
    CONF_V3_PRIV_PROTOCOL,
    CONF_V3_USERNAME,
    DEFAULT_COMMUNITY_READ,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SNMP_VERSION_2C,
    SNMP_VERSION_3,
    SNMP_VERSIONS,
    V3_AUTH_NONE,
    V3_AUTH_PROTOCOLS,
    V3_AUTH_SHA256,
    V3_PRIV_AES128,
    V3_PRIV_NONE,
    V3_PRIV_PROTOCOLS,
)

_LOGGER = logging.getLogger(__name__)


# ── Schema factories — always seeded with current values so form isn't reset ──

def _user_schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
        vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)):
            vol.All(int, vol.Range(min=1, max=65535)),
        vol.Optional(CONF_SNMP_VERSION, default=defaults.get(CONF_SNMP_VERSION, SNMP_VERSION_2C)):
            vol.In(SNMP_VERSIONS),
        vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
            vol.All(int, vol.Range(min=10, max=3600)),
    })


def _community_schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_COMMUNITY_READ,
            default=defaults.get(CONF_COMMUNITY_READ, DEFAULT_COMMUNITY_READ)): str,
        vol.Optional(CONF_COMMUNITY_WRITE,
            default=defaults.get(CONF_COMMUNITY_WRITE) or ""): str,
    })


def _v3_schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_V3_USERNAME,
            default=defaults.get(CONF_V3_USERNAME, "")): str,
        vol.Optional(CONF_V3_AUTH_PROTOCOL,
            default=defaults.get(CONF_V3_AUTH_PROTOCOL, V3_AUTH_SHA256)):
            vol.In(V3_AUTH_PROTOCOLS),
        vol.Optional(CONF_V3_AUTH_KEY,
            default=defaults.get(CONF_V3_AUTH_KEY, "")): str,
        vol.Optional(CONF_V3_PRIV_PROTOCOL,
            default=defaults.get(CONF_V3_PRIV_PROTOCOL, V3_PRIV_AES128)):
            vol.In(V3_PRIV_PROTOCOLS),
        vol.Optional(CONF_V3_PRIV_KEY,
            default=defaults.get(CONF_V3_PRIV_KEY, "")): str,
        vol.Optional(CONF_V3_CONTEXT_NAME,
            default=defaults.get(CONF_V3_CONTEXT_NAME, "")): str,
    })


def _make_client(data: dict[str, Any]):
    from .snmp_client import SNMPSwitchClient  # lazy
    return SNMPSwitchClient(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        community_read=data.get(CONF_COMMUNITY_READ, DEFAULT_COMMUNITY_READ),
        community_write=data.get(CONF_COMMUNITY_WRITE) or None,
        snmp_version=data.get(CONF_SNMP_VERSION, SNMP_VERSION_2C),
        v3_username=data.get(CONF_V3_USERNAME, ""),
        v3_auth_protocol=data.get(CONF_V3_AUTH_PROTOCOL, V3_AUTH_NONE),
        v3_auth_key=data.get(CONF_V3_AUTH_KEY, ""),
        v3_priv_protocol=data.get(CONF_V3_PRIV_PROTOCOL, V3_PRIV_NONE),
        v3_priv_key=data.get(CONF_V3_PRIV_KEY, ""),
        v3_context_name=data.get(CONF_V3_CONTEXT_NAME, ""),
    )


class SNMPSwitchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Step 1 (user):      Host, Port, SNMP-Version, Name, Interval
    Step 2a (community): v1/v2c Community Strings + connection test
    Step 2b (v3):        SNMPv3 USM Credentials + connection test
    """

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    # ── Step 1 ─────────────────────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        if user_input is not None:
            self._data.update(user_input)

            # Early duplicate check before connection test
            unique_id = (
                f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}"
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            if user_input.get(CONF_SNMP_VERSION) == SNMP_VERSION_3:
                return await self.async_step_v3()
            return await self.async_step_community()

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self._data),
        )

    # ── Step 2a: community ─────────────────────────────────────────────────

    async def async_step_community(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            merged = {**self._data, **user_input}
            merged[CONF_COMMUNITY_WRITE] = user_input.get(CONF_COMMUNITY_WRITE) or None

            try:
                client = _make_client(merged)
                ok = await client.test_connection()
                if ok:
                    self._data = merged
                    return await self._finish(client)
                _LOGGER.warning(
                    "snmp_switch: cannot_connect to %s:%s — "
                    "sysDescr returned empty. Check host, port and community string.",
                    merged.get(CONF_HOST), merged.get(CONF_PORT),
                )
                errors["base"] = "cannot_connect"
            except Exception as exc:
                _LOGGER.exception(
                    "snmp_switch: exception during connection test to %s:%s — %s",
                    merged.get(CONF_HOST), merged.get(CONF_PORT), exc,
                )
                errors["base"] = "cannot_connect"

            # Re-render with the values the user just typed (not reset!)
            return self.async_show_form(
                step_id="community",
                data_schema=_community_schema(user_input),
                errors=errors,
            )

        return self.async_show_form(
            step_id="community",
            data_schema=_community_schema(self._data),
        )

    # ── Step 2b: v3 ────────────────────────────────────────────────────────

    async def async_step_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            has_auth = (
                user_input.get(CONF_V3_AUTH_PROTOCOL, V3_AUTH_NONE) != V3_AUTH_NONE
                and bool(user_input.get(CONF_V3_AUTH_KEY, "").strip())
            )
            has_priv = (
                user_input.get(CONF_V3_PRIV_PROTOCOL, V3_PRIV_NONE) != V3_PRIV_NONE
                and bool(user_input.get(CONF_V3_PRIV_KEY, "").strip())
            )

            if has_priv and not has_auth:
                errors[CONF_V3_AUTH_KEY] = "priv_requires_auth"
            else:
                merged = {**self._data, **user_input}
                try:
                    client = _make_client(merged)
                    ok = await client.test_connection()
                    if ok:
                        self._data = merged
                        return await self._finish(client)
                    _LOGGER.warning(
                        "snmp_switch: cannot_connect to %s:%s via SNMPv3 — "
                        "sysDescr returned empty. Check host, port, username, "
                        "auth-protocol '%s', priv-protocol '%s'.",
                        merged.get(CONF_HOST), merged.get(CONF_PORT),
                        user_input.get(CONF_V3_AUTH_PROTOCOL),
                        user_input.get(CONF_V3_PRIV_PROTOCOL),
                    )
                    errors["base"] = "cannot_connect"
                except Exception as exc:
                    _LOGGER.exception(
                        "snmp_switch: exception during SNMPv3 connection test to %s:%s "
                        "(user=%s, auth=%s, priv=%s) — %s",
                        merged.get(CONF_HOST), merged.get(CONF_PORT),
                        user_input.get(CONF_V3_USERNAME),
                        user_input.get(CONF_V3_AUTH_PROTOCOL),
                        user_input.get(CONF_V3_PRIV_PROTOCOL),
                        exc,
                    )
                    errors["base"] = "cannot_connect"

            # Re-render with values intact
            return self.async_show_form(
                step_id="v3",
                data_schema=_v3_schema(user_input),
                errors=errors,
            )

        return self.async_show_form(
            step_id="v3",
            data_schema=_v3_schema(self._data),
        )

    # ── Finish ─────────────────────────────────────────────────────────────

    async def _finish(self, client) -> config_entries.FlowResult:
        unique_id = (
            f"{self._data[CONF_HOST]}:{self._data.get(CONF_PORT, DEFAULT_PORT)}"
        )
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        title = self._data.get(CONF_NAME, "").strip()
        if not title:
            try:
                info = await client.get_system_info()
                title = info.get("name") or self._data[CONF_HOST]
            except Exception:
                title = self._data[CONF_HOST]

        _LOGGER.info("snmp_switch: entry created — %s (%s)", title, unique_id)
        return self.async_create_entry(title=title, data=self._data)

    # ── Reconfigure Flow ───────────────────────────────────────────────────

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle reconfiguration of an existing entry."""
        entry = self._get_reconfigure_entry()
        if not self._data:
            self._data = dict(entry.data)

        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_SNMP_VERSION) == SNMP_VERSION_3:
                return await self.async_step_reconfigure_v3()
            return await self.async_step_reconfigure_community()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(self._data),
        )

    async def async_step_reconfigure_community(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Reconfigure community credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            merged = {**self._data, **user_input}
            merged[CONF_COMMUNITY_WRITE] = user_input.get(CONF_COMMUNITY_WRITE) or None

            try:
                client = _make_client(merged)
                ok = await client.test_connection()
                if ok:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data=merged,
                    )
                _LOGGER.warning(
                    "snmp_switch: cannot_connect during reconfigure to %s:%s",
                    merged.get(CONF_HOST), merged.get(CONF_PORT),
                )
                errors["base"] = "cannot_connect"
            except Exception as exc:
                _LOGGER.exception(
                    "snmp_switch: exception during reconfigure test to %s:%s — %s",
                    merged.get(CONF_HOST), merged.get(CONF_PORT), exc,
                )
                errors["base"] = "cannot_connect"

            return self.async_show_form(
                step_id="reconfigure_community",
                data_schema=_community_schema(user_input),
                errors=errors,
            )

        return self.async_show_form(
            step_id="reconfigure_community",
            data_schema=_community_schema(self._data),
        )

    async def async_step_reconfigure_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Reconfigure SNMPv3 credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            has_auth = (
                user_input.get(CONF_V3_AUTH_PROTOCOL, V3_AUTH_NONE) != V3_AUTH_NONE
                and bool(user_input.get(CONF_V3_AUTH_KEY, "").strip())
            )
            has_priv = (
                user_input.get(CONF_V3_PRIV_PROTOCOL, V3_PRIV_NONE) != V3_PRIV_NONE
                and bool(user_input.get(CONF_V3_PRIV_KEY, "").strip())
            )

            if has_priv and not has_auth:
                errors[CONF_V3_AUTH_KEY] = "priv_requires_auth"
            else:
                merged = {**self._data, **user_input}
                try:
                    client = _make_client(merged)
                    ok = await client.test_connection()
                    if ok:
                        return self.async_update_reload_and_abort(
                            self._get_reconfigure_entry(),
                            data=merged,
                        )
                    _LOGGER.warning(
                        "snmp_switch: cannot_connect during reconfigure to %s:%s via SNMPv3",
                        merged.get(CONF_HOST), merged.get(CONF_PORT),
                    )
                    errors["base"] = "cannot_connect"
                except Exception as exc:
                    _LOGGER.exception(
                        "snmp_switch: exception during SNMPv3 reconfigure test to %s:%s — %s",
                        merged.get(CONF_HOST), merged.get(CONF_PORT), exc,
                    )
                    errors["base"] = "cannot_connect"

            return self.async_show_form(
                step_id="reconfigure_v3",
                data_schema=_v3_schema(user_input),
                errors=errors,
            )

        return self.async_show_form(
            step_id="reconfigure_v3",
            data_schema=_v3_schema(self._data),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SNMPSwitchOptionsFlow:
        return SNMPSwitchOptionsFlow()


# ── Options Flow ───────────────────────────────────────────────────────────

class SNMPSwitchOptionsFlow(config_entries.OptionsFlow):
    """Options flow — self.config_entry is set automatically by HA."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        current = {**self.config_entry.data, **self.config_entry.options}
        version = current.get(CONF_SNMP_VERSION, SNMP_VERSION_2C)

        if user_input is not None:
            if not user_input.get(CONF_COMMUNITY_WRITE):
                user_input[CONF_COMMUNITY_WRITE] = None
            return self.async_create_entry(title="", data=user_input)

        if version == SNMP_VERSION_3:
            schema = vol.Schema({
                vol.Optional(CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                    vol.All(int, vol.Range(min=10, max=3600)),
                vol.Optional(CONF_V3_AUTH_KEY,
                    default=current.get(CONF_V3_AUTH_KEY, "")): str,
                vol.Optional(CONF_V3_PRIV_KEY,
                    default=current.get(CONF_V3_PRIV_KEY, "")): str,
            })
        else:
            schema = vol.Schema({
                vol.Optional(CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                    vol.All(int, vol.Range(min=10, max=3600)),
                vol.Optional(CONF_COMMUNITY_WRITE,
                    default=current.get(CONF_COMMUNITY_WRITE) or ""): str,
            })

        return self.async_show_form(step_id="init", data_schema=schema)
