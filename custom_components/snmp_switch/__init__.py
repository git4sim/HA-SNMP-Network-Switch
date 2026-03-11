"""SNMP Network Switch Integration for Home Assistant."""
from __future__ import annotations

import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall

# !! IMPORTANT !!
# Do NOT import snmp_client, coordinator, or any module that imports pysnmp
# at the top level of this file. Python loads __init__.py as the package
# initialiser before config_flow.py, so a top-level pysnmp import here will
# crash the entire package load and HA will report "Invalid handler specified"
# even before the config flow UI opens.
# All imports of those modules must stay inside async_setup_entry() and the
# service handlers below.

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
    PLATFORMS,
    SNMP_VERSION_2C,
    V3_AUTH_NONE,
    V3_PRIV_NONE,
)

_LOGGER = logging.getLogger(__name__)


def _build_client(data: dict):
    """Build SNMPSwitchClient — lazy import keeps pysnmp out of package init."""
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SNMP Network Switch from a config entry."""
    from .coordinator import SNMPSwitchCoordinator  # lazy

    data = {**entry.data, **entry.options}
    client = _build_client(data)

    coordinator = SNMPSwitchCoordinator(
        hass=hass,
        client=client,
        name=data.get(CONF_NAME) or data[CONF_HOST],
        scan_interval=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry after options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


def _register_services(hass: HomeAssistant) -> None:
    """Register HA services (idempotent)."""

    async def _get_coordinator(entry_id: str):
        return hass.data.get(DOMAIN, {}).get(entry_id)

    async def svc_set_port_alias(call: ServiceCall) -> None:
        coord = await _get_coordinator(call.data["entry_id"])
        if coord:
            await coord.client.set_port_alias(call.data["if_index"], call.data["alias"])
            await coord.async_request_refresh()

    async def svc_set_sys_contact(call: ServiceCall) -> None:
        coord = await _get_coordinator(call.data["entry_id"])
        if coord:
            await coord.client.set_sys_contact(call.data["contact"])
            await coord.async_request_refresh()

    async def svc_set_sys_location(call: ServiceCall) -> None:
        coord = await _get_coordinator(call.data["entry_id"])
        if coord:
            await coord.client.set_sys_location(call.data["location"])
            await coord.async_request_refresh()

    async def svc_set_sys_name(call: ServiceCall) -> None:
        coord = await _get_coordinator(call.data["entry_id"])
        if coord:
            await coord.client.set_sys_name(call.data["name"])
            await coord.async_request_refresh()

    svc = hass.services
    if not svc.has_service(DOMAIN, "set_port_alias"):
        svc.async_register(DOMAIN, "set_port_alias", svc_set_port_alias,
            schema=vol.Schema({
                vol.Required("entry_id"): cv.string,
                vol.Required("if_index"): vol.All(int, vol.Range(min=1)),
                vol.Required("alias"): cv.string,
            }))
    if not svc.has_service(DOMAIN, "set_sys_contact"):
        svc.async_register(DOMAIN, "set_sys_contact", svc_set_sys_contact,
            schema=vol.Schema({
                vol.Required("entry_id"): cv.string,
                vol.Required("contact"): cv.string,
            }))
    if not svc.has_service(DOMAIN, "set_sys_location"):
        svc.async_register(DOMAIN, "set_sys_location", svc_set_sys_location,
            schema=vol.Schema({
                vol.Required("entry_id"): cv.string,
                vol.Required("location"): cv.string,
            }))
    if not svc.has_service(DOMAIN, "set_sys_name"):
        svc.async_register(DOMAIN, "set_sys_name", svc_set_sys_name,
            schema=vol.Schema({
                vol.Required("entry_id"): cv.string,
                vol.Required("name"): cv.string,
            }))
