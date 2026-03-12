"""Text-Entities für beschreibbare SNMP-Felder."""
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
    """Text-Entities einrichten (nur bei Write-Zugriff)."""
    coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.has_write_access:
        _LOGGER.debug("Kein Write-Zugriff – Text-Entities werden nicht erstellt")
        return

    entities: list[TextEntity] = []

    # System-Felder (beschreibbar)
    entities.extend([
        SNMPSystemText(coordinator, entry, "contact", "Kontakt", "mdi:account", "set_sys_contact"),
        SNMPSystemText(coordinator, entry, "name", "Systemname", "mdi:tag-outline", "set_sys_name"),
        SNMPSystemText(coordinator, entry, "location", "Standort", "mdi:map-marker", "set_sys_location"),
    ])

    # Port-Alias (pro Port, beschreibbar)
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


class SNMPSystemText(CoordinatorEntity[SNMPSwitchCoordinator], TextEntity):
    """Beschreibbares Text-Entity für System-Felder (sysContact, sysName, sysLocation)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 255

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        key: str,
        label: str,
        icon: str,
        setter: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._setter = setter
        host = entry.data.get(CONF_NAME) or entry.data[CONF_HOST]
        self._attr_name = f"{host} {label}"
        self._attr_unique_id = f"{entry.entry_id}_sys_{key}_text"
        self._attr_icon = icon
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        return self.coordinator.get_system_value(self._key)

    async def async_set_value(self, value: str) -> None:
        """Wert via SNMP SET schreiben."""
        setter_fn = getattr(self.coordinator.client, self._setter)
        success = await setter_fn(value)
        if success:
            _LOGGER.info("System %s auf '%s' gesetzt", self._key, value)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Konnte System %s nicht setzen", self._key)


class SNMPPortAliasText(CoordinatorEntity[SNMPSwitchCoordinator], TextEntity):
    """Beschreibbares Text-Entity für Port-Alias (ifAlias)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max = 64

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        if_index: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._if_index = if_index
        host = entry.data.get(CONF_NAME) or entry.data[CONF_HOST]
        iface = coordinator.get_interface(if_index) or {}
        port_name = iface.get("name") or iface.get("description") or f"Port {if_index}"
        self._attr_name = f"{host} {port_name} Alias"
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_alias_text"
        self._attr_icon = "mdi:label-outline"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            return iface.get("alias", "")
        return None

    async def async_set_value(self, value: str) -> None:
        """Port-Alias via SNMP SET schreiben."""
        success = await self.coordinator.client.set_port_alias(self._if_index, value)
        if success:
            _LOGGER.info("Port %d Alias auf '%s' gesetzt", self._if_index, value)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Konnte Alias für Port %d nicht setzen", self._if_index)
