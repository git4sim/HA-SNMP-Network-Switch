"""SNMP Network Switch Integration für Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_COMMUNITY_READ,
    CONF_COMMUNITY_WRITE,
    CONF_SCAN_INTERVAL,
    CONF_SNMP_VERSION,
    DEFAULT_COMMUNITY_READ,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SNMP_VERSION_2C,
)
from .coordinator import SNMPSwitchCoordinator
from .snmp_client import SNMPSwitchClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration einrichten aus einem Config Entry."""
    data = {**entry.data, **entry.options}

    client = SNMPSwitchClient(
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        community_read=data.get(CONF_COMMUNITY_READ, DEFAULT_COMMUNITY_READ),
        community_write=data.get(CONF_COMMUNITY_WRITE) or None,
        snmp_version=data.get(CONF_SNMP_VERSION, SNMP_VERSION_2C),
    )

    coordinator = SNMPSwitchCoordinator(
        hass=hass,
        client=client,
        name=data.get(CONF_NAME) or data[CONF_HOST],
        scan_interval=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Services registrieren
    _register_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration entladen."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Integration neu laden (nach Options-Änderung)."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


def _register_services(hass: HomeAssistant) -> None:
    """Home Assistant Services registrieren."""

    async def service_set_port_alias(call: ServiceCall) -> None:
        """Service: Port-Beschreibung setzen."""
        entry_id = call.data["entry_id"]
        if_index = call.data["if_index"]
        alias = call.data["alias"]
        coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN].get(entry_id)
        if coordinator:
            await coordinator.client.set_port_alias(if_index, alias)
            await coordinator.async_request_refresh()

    async def service_set_sys_contact(call: ServiceCall) -> None:
        """Service: sysContact setzen."""
        entry_id = call.data["entry_id"]
        contact = call.data["contact"]
        coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN].get(entry_id)
        if coordinator:
            await coordinator.client.set_sys_contact(contact)
            await coordinator.async_request_refresh()

    async def service_set_sys_location(call: ServiceCall) -> None:
        """Service: sysLocation setzen."""
        entry_id = call.data["entry_id"]
        location = call.data["location"]
        coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN].get(entry_id)
        if coordinator:
            await coordinator.client.set_sys_location(location)
            await coordinator.async_request_refresh()

    async def service_set_sys_name(call: ServiceCall) -> None:
        """Service: sysName setzen."""
        entry_id = call.data["entry_id"]
        name = call.data["name"]
        coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN].get(entry_id)
        if coordinator:
            await coordinator.client.set_sys_name(name)
            await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, "set_port_alias"):
        hass.services.async_register(
            DOMAIN,
            "set_port_alias",
            service_set_port_alias,
            schema=vol.Schema({
                vol.Required("entry_id"): cv.string,
                vol.Required("if_index"): vol.All(int, vol.Range(min=1)),
                vol.Required("alias"): cv.string,
            }),
        )

    if not hass.services.has_service(DOMAIN, "set_sys_contact"):
        hass.services.async_register(
            DOMAIN,
            "set_sys_contact",
            service_set_sys_contact,
            schema=vol.Schema({
                vol.Required("entry_id"): cv.string,
                vol.Required("contact"): cv.string,
            }),
        )

    if not hass.services.has_service(DOMAIN, "set_sys_location"):
        hass.services.async_register(
            DOMAIN,
            "set_sys_location",
            service_set_sys_location,
            schema=vol.Schema({
                vol.Required("entry_id"): cv.string,
                vol.Required("location"): cv.string,
            }),
        )

    if not hass.services.has_service(DOMAIN, "set_sys_name"):
        hass.services.async_register(
            DOMAIN,
            "set_sys_name",
            service_set_sys_name,
            schema=vol.Schema({
                vol.Required("entry_id"): cv.string,
                vol.Required("name"): cv.string,
            }),
        )
