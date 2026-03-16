"""Switch entities for SNMP Network Switch ports."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, IF_OPER_STATUS_MAP, format_speed
from .coordinator import SNMPSwitchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities (only if write access is available)."""
    coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.has_write_access:
        _LOGGER.info("No write access – port switches will not be created")
        return

    entities: list[SwitchEntity] = []

    if coordinator.data and "interfaces" in coordinator.data:
        for if_index in coordinator.data["interfaces"]:
            entities.append(SNMPPortSwitch(coordinator, entry, if_index))

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


class SNMPPortSwitch(CoordinatorEntity[SNMPSwitchCoordinator], SwitchEntity):
    """Switch entity to enable/disable a port (ifAdminStatus)."""

    _attr_has_entity_name = True
    _attr_translation_key = "port_switch"

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        if_index: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._if_index = if_index
        self._attr_unique_id = f"{entry.entry_id}_port_{if_index}_switch"
        self._attr_device_info = _device_info(entry)
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def is_on(self) -> bool | None:
        """True if admin status = up (1)."""
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            return iface.get("admin_status") == 1
        return None

    @property
    def icon(self) -> str:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            oper = iface.get("oper_status", 2)
            admin = iface.get("admin_status", 2)
            if admin == 1 and oper == 1:
                return "mdi:ethernet"
            elif admin == 1 and oper != 1:
                return "mdi:ethernet-off"
            else:
                return "mdi:power-plug-off"
        return "mdi:ethernet"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        iface = self.coordinator.get_interface(self._if_index)
        if not iface:
            return {}
        return {
            "if_index": self._if_index,
            "description": iface.get("description", ""),
            "alias": iface.get("alias", ""),
            "mac": iface.get("mac", ""),
            "speed": format_speed(iface.get("speed_mbps", 0)),
            "oper_status": IF_OPER_STATUS_MAP.get(iface.get("oper_status", 2), "unknown"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable port (ifAdminStatus = up)."""
        success = await self.coordinator.client.set_port_admin_status(self._if_index, True)
        if success:
            _LOGGER.info("Port %d enabled", self._if_index)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Could not enable port %d", self._if_index)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable port (ifAdminStatus = down)."""
        success = await self.coordinator.client.set_port_admin_status(self._if_index, False)
        if success:
            _LOGGER.info("Port %d disabled", self._if_index)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Could not disable port %d", self._if_index)
