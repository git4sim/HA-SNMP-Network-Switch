"""Config Flow for SNMP Network Switch — supports v1, v2c, v3."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError

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
from .snmp_client import SNMPSwitchClient

_LOGGER = logging.getLogger(__name__)

# ── Schemas ────────────────────────────────────────────────────────────────

STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
    vol.Optional(CONF_SNMP_VERSION, default=SNMP_VERSION_2C): vol.In(SNMP_VERSIONS),
    vol.Optional(CONF_NAME, default=""): str,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        int, vol.Range(min=10, max=3600)
    ),
})

STEP_COMMUNITY_SCHEMA = vol.Schema({
    vol.Optional(CONF_COMMUNITY_READ, default=DEFAULT_COMMUNITY_READ): str,
    vol.Optional(CONF_COMMUNITY_WRITE, default=""): str,
})

STEP_V3_SCHEMA = vol.Schema({
    vol.Required(CONF_V3_USERNAME): str,
    vol.Optional(CONF_V3_AUTH_PROTOCOL, default=V3_AUTH_SHA256): vol.In(V3_AUTH_PROTOCOLS),
    vol.Optional(CONF_V3_AUTH_KEY, default=""): str,
    vol.Optional(CONF_V3_PRIV_PROTOCOL, default=V3_PRIV_AES128): vol.In(V3_PRIV_PROTOCOLS),
    vol.Optional(CONF_V3_PRIV_KEY, default=""): str,
    vol.Optional(CONF_V3_CONTEXT_NAME, default=""): str,
})


def _make_client(data: dict[str, Any]) -> SNMPSwitchClient:
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
    """Multi-step Config Flow: user → community OR v3 → done."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    # ── Step 1: host + version ─────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_SNMP_VERSION) == SNMP_VERSION_3:
                # Proceed to v3 credentials step
                return self.async_show_form(
                    step_id="v3",
                    data_schema=STEP_V3_SCHEMA,
                    errors={},
                )
            # Proceed to community step
            return self.async_show_form(
                step_id="community",
                data_schema=STEP_COMMUNITY_SCHEMA,
                errors={},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    # ── Step 2a: v1/v2c community ──────────────────────────────────────────

    async def async_step_community(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            # Normalise: empty string → None
            if not self._data.get(CONF_COMMUNITY_WRITE):
                self._data[CONF_COMMUNITY_WRITE] = None

            # Test connection
            try:
                client = _make_client(self._data)
                if not await client.test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    return await self._create_entry(client)
            except Exception:
                _LOGGER.exception("Error connecting to switch")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="community",
            data_schema=STEP_COMMUNITY_SCHEMA,
            errors=errors,
        )

    # ── Step 2b: SNMPv3 USM ───────────────────────────────────────────────

    async def async_step_v3(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate: privacy requires authentication
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
                self._data.update(user_input)
                try:
                    client = _make_client(self._data)
                    if not await client.test_connection():
                        errors["base"] = "cannot_connect"
                    else:
                        return await self._create_entry(client)
                except Exception:
                    _LOGGER.exception("Error connecting to switch via SNMPv3")
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="v3",
            data_schema=STEP_V3_SCHEMA,
            errors=errors,
        )

    # ── Helper: finalize entry ─────────────────────────────────────────────

    async def _create_entry(self, client: SNMPSwitchClient) -> config_entries.FlowResult:
        """Set unique ID and create the config entry."""
        unique_id = f"{self._data[CONF_HOST]}:{self._data.get(CONF_PORT, DEFAULT_PORT)}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        system_info = await client.get_system_info()
        title = (
            self._data.get(CONF_NAME)
            or system_info.get("name")
            or self._data[CONF_HOST]
        )
        return self.async_create_entry(title=title, data=self._data)

    # ── Options flow ───────────────────────────────────────────────────────

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SNMPSwitchOptionsFlow:
        return SNMPSwitchOptionsFlow(config_entry)


class SNMPSwitchOptionsFlow(config_entries.OptionsFlow):
    """Options flow — adjust scan interval and write credentials."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

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
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=10, max=3600)),
                vol.Optional(
                    CONF_V3_AUTH_KEY,
                    default=current.get(CONF_V3_AUTH_KEY, ""),
                ): str,
                vol.Optional(
                    CONF_V3_PRIV_KEY,
                    default=current.get(CONF_V3_PRIV_KEY, ""),
                ): str,
            })
        else:
            schema = vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=10, max=3600)),
                vol.Optional(
                    CONF_COMMUNITY_WRITE,
                    default=current.get(CONF_COMMUNITY_WRITE, ""),
                ): str,
            })

        return self.async_show_form(step_id="init", data_schema=schema)
