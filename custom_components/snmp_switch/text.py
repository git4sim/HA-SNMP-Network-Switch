"""Text entities for writable SNMP fields."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SNMPSwitchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up text entities (only if write access is available)."""
    coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.has_write_access:
        _LOGGER.debug("No write access – text entities will not be created")
        return

    entities: list[TextEntity] = []

    # System fields (writable)
    entities.extend([
        SNMPSystemText(coordinator, entry, "contact", "sys_contact_text", "mdi:account", "set_sys_contact"),
        SNMPSystemText(coordinator, entry, "name", "sys_name_text", "mdi:tag-outline", "set_sys_name"),
        SNMPSystemText(coordinator, entry, "location", "sys_location_text", "mdi:map-marker", "set_sys_location"),
    ])

    # Port alias (per port, writable)
    if coordinator.data and "interfaces" in coordinator.data:
        for if_index in coordinator.data["interfaces"]:
            entities.append(SNMPPortAliasText(coordinator, entry, if_index))

    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    data = entry.data
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=data.get(CONF_NAME) or data[CONF_HOST],
        manufacturer="Network Switch",
        model="SNMP Managed Switch",
    )


def _port_label(coordinator: SNMPSwitchCoordinator, if_index: int) -> str:
    iface = coordinator.get_interface(if_index) or {}
    label = iface.get("name") or iface.get("description")
    if label:
        if label.isdigit():
            return f"Port {label}"
        return label
    return f"Port {if_index}"


class SNMPSystemText(CoordinatorEntity[SNMPSwitchCoordinator], TextEntity):
    """Writable text entity for system fields (sysContact, sysName, sysLocation)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 255

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        key: str,
        translation_key: str,
        icon: str,
        setter: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._setter = setter
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_sys_{key}_text"
        self._attr_icon = icon
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        return self.coordinator.get_system_value(self._key)

    async def async_set_value(self, value: str) -> None:
        """Write value via SNMP SET."""
        setter_fn = getattr(self.coordinator.client, self._setter)
        success = await setter_fn(value)
        if success:
            _LOGGER.info("System %s set to '%s'", self._key, value)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Could not set system %s", self._key)


class SNMPPortAliasText(CoordinatorEntity[SNMPSwitchCoordinator], TextEntity):
    """Writable text entity for port alias (ifAlias)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 64
    _attr_translation_key = "port_alias_text"

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        if_index: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._if_index = if_index
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_alias_text"
        self._attr_icon = "mdi:label-outline"
        self._attr_device_info = _device_info(entry)
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def native_value(self) -> str | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            return iface.get("alias", "")
        return None

    async def async_set_value(self, value: str) -> None:
        """Write port alias via SNMP SET."""
        success = await self.coordinator.client.set_port_alias(self._if_index, value)
        if success:
            _LOGGER.info("Port %d alias set to '%s'", self._if_index, value)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Could not set alias for port %d", self._if_index)
