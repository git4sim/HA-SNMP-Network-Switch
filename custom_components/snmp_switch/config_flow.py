"""Config Flow für SNMP Network Switch."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_COMMUNITY_READ,
    CONF_COMMUNITY_WRITE,
    CONF_SCAN_INTERVAL,
    CONF_SNMP_VERSION,
    DEFAULT_COMMUNITY_READ,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SNMP_VERSION_2C,
    SNMP_VERSIONS,
)
from .snmp_client import SNMPSwitchClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
        vol.Optional(CONF_COMMUNITY_READ, default=DEFAULT_COMMUNITY_READ): str,
        vol.Optional(CONF_COMMUNITY_WRITE, default=""): str,
        vol.Optional(CONF_SNMP_VERSION, default=SNMP_VERSION_2C): vol.In(SNMP_VERSIONS),
        vol.Optional(CONF_NAME, default=""): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=10, max=3600)
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Eingabe validieren und Verbindung testen."""
    client = SNMPSwitchClient(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        community_read=data.get(CONF_COMMUNITY_READ, DEFAULT_COMMUNITY_READ),
        community_write=data.get(CONF_COMMUNITY_WRITE) or None,
        snmp_version=data.get(CONF_SNMP_VERSION, SNMP_VERSION_2C),
    )

    if not await client.test_connection():
        raise CannotConnect

    system_info = await client.get_system_info()
    detected_name = system_info.get("name") or data[CONF_HOST]

    return {"title": data.get(CONF_NAME) or detected_name}


class SNMPSwitchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für die SNMP Switch Integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Erster Schritt: Benutzereingabe."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Eindeutige ID: Host + Port
                unique_id = f"{user_input[CONF_HOST]}:{user_input.get(CONF_PORT, DEFAULT_PORT)}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unbekannter Fehler beim Konfigurieren")
                errors["base"] = "unknown"
            else:
                # Community String bereinigen
                if not user_input.get(CONF_COMMUNITY_WRITE):
                    user_input[CONF_COMMUNITY_WRITE] = None

                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> SNMPSwitchOptionsFlow:
        """Options Flow Handler zurückgeben."""
        return SNMPSwitchOptionsFlow(config_entry)


class SNMPSwitchOptionsFlow(config_entries.OptionsFlow):
    """Options Flow zum Anpassen der Einstellungen."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialisierung."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Options anzeigen und speichern."""
        if user_input is not None:
            if not user_input.get(CONF_COMMUNITY_WRITE):
                user_input[CONF_COMMUNITY_WRITE] = None
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=10, max=3600)),
                    vol.Optional(
                        CONF_COMMUNITY_WRITE,
                        default=current.get(CONF_COMMUNITY_WRITE, ""),
                    ): str,
                }
            ),
        )


class CannotConnect(Exception):
    """Fehler: Verbindung nicht möglich."""
