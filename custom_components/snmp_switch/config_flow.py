"""Config Flow for SNMP Network Switch — supports v1, v2c, v3."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback

# NOTE: snmp_client is NOT imported at module level on purpose.
# pysnmp (external requirement) may not yet be installed when HA first loads
# the config flow module. A top-level import causes ImportError → HA reports
# "invalid handler specified". We import SNMPSwitchClient lazily inside methods.

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


def _full_schema(snmp_version: str = SNMP_VERSION_2C) -> vol.Schema:
    """Return the appropriate schema based on selected SNMP version."""
    base = {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            int, vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_SNMP_VERSION, default=snmp_version): vol.In(SNMP_VERSIONS),
        vol.Optional(CONF_NAME, default=""): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=10, max=3600)
        ),
    }

    if snmp_version == SNMP_VERSION_3:
        base.update({
            vol.Required(CONF_V3_USERNAME): str,
            vol.Optional(CONF_V3_AUTH_PROTOCOL, default=V3_AUTH_SHA256): vol.In(
                V3_AUTH_PROTOCOLS
            ),
            vol.Optional(CONF_V3_AUTH_KEY, default=""): str,
            vol.Optional(CONF_V3_PRIV_PROTOCOL, default=V3_PRIV_AES128): vol.In(
                V3_PRIV_PROTOCOLS
            ),
            vol.Optional(CONF_V3_PRIV_KEY, default=""): str,
            vol.Optional(CONF_V3_CONTEXT_NAME, default=""): str,
        })
    else:
        base.update({
            vol.Optional(CONF_COMMUNITY_READ, default=DEFAULT_COMMUNITY_READ): str,
            vol.Optional(CONF_COMMUNITY_WRITE, default=""): str,
        })

    return vol.Schema(base)


def _make_client(data: dict[str, Any]):
    """Build SNMPSwitchClient with lazy import."""
    from .snmp_client import SNMPSwitchClient  # lazy – pysnmp must be installed first
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
    """Single-step Config Flow with version-adaptive schema."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        # Track which version was last selected so we can rebuild the schema
        current_version = SNMP_VERSION_2C

        if user_input is not None:
            current_version = user_input.get(CONF_SNMP_VERSION, SNMP_VERSION_2C)

            # If user just switched to v3 but hasn't filled v3 fields yet,
            # redisplay with v3 schema (no connection test yet)
            if (
                current_version == SNMP_VERSION_3
                and not user_input.get(CONF_V3_USERNAME, "").strip()
            ):
                return self.async_show_form(
                    step_id="user",
                    data_schema=_full_schema(SNMP_VERSION_3),
                    errors={"base": "v3_username_required"},
                    description_placeholders={"version": "v3"},
                )

            # Validate: privacy requires authentication for v3
            if current_version == SNMP_VERSION_3:
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
                    return self.async_show_form(
                        step_id="user",
                        data_schema=_full_schema(SNMP_VERSION_3),
                        errors=errors,
                    )

            # Normalise community write
            if not user_input.get(CONF_COMMUNITY_WRITE):
                user_input[CONF_COMMUNITY_WRITE] = None

            # Test connection
            try:
                client = _make_client(user_input)
                if not await client.test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    # Determine unique ID and title
                    unique_id = f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    system_info = await client.get_system_info()
                    title = (
                        user_input.get(CONF_NAME)
                        or system_info.get("name")
                        or user_input[CONF_HOST]
                    )
                    return self.async_create_entry(title=title, data=user_input)
            except Exception:
                _LOGGER.exception("Unexpected error testing SNMP connection")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=_full_schema(current_version),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SNMPSwitchOptionsFlow:
        return SNMPSwitchOptionsFlow(config_entry)


class SNMPSwitchOptionsFlow(config_entries.OptionsFlow):
    """Options flow — adjust scan interval and credentials."""

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
                    default=current.get(CONF_COMMUNITY_WRITE, "") or "",
                ): str,
            })

        return self.async_show_form(step_id="init", data_schema=schema)
