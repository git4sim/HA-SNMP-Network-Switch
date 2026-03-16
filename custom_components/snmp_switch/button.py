"""Button entities for SNMP Network Switch."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SNMPSwitchCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SNMPRefreshButton(coordinator, entry)])


class SNMPRefreshButton(CoordinatorEntity[SNMPSwitchCoordinator], ButtonEntity):
    """Button to manually refresh SNMP data."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        host = entry.data.get(CONF_NAME) or entry.data[CONF_HOST]
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_icon = "mdi:refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=host,
            manufacturer="Network Switch",
            model="SNMP Managed Switch",
        )

    async def async_press(self) -> None:
        """Refresh data immediately."""
        await self.coordinator.async_request_refresh()
