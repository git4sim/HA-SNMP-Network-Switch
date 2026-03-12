"""Switch-Entities für SNMP Network Switch Ports."""
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
    """Switch-Entities einrichten (nur wenn Write-Zugriff vorhanden)."""
    coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.has_write_access:
        _LOGGER.info("Kein Write-Zugriff – Port-Switches werden nicht erstellt")
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


class SNMPPortSwitch(CoordinatorEntity[SNMPSwitchCoordinator], SwitchEntity):
    """Switch-Entity zum Ein-/Ausschalten eines Ports (ifAdminStatus)."""

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
        self._attr_name = f"{host} {port_name}"
        self._attr_unique_id = f"{entry.entry_id}_port_{if_index}_switch"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool | None:
        """True wenn Admin-Status = up (1)."""
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
        """Port einschalten (ifAdminStatus = up)."""
        success = await self.coordinator.client.set_port_admin_status(self._if_index, True)
        if success:
            _LOGGER.info("Port %d eingeschaltet", self._if_index)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Konnte Port %d nicht einschalten", self._if_index)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Port ausschalten (ifAdminStatus = down)."""
        success = await self.coordinator.client.set_port_admin_status(self._if_index, False)
        if success:
            _LOGGER.info("Port %d ausgeschaltet", self._if_index)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Konnte Port %d nicht ausschalten", self._if_index)
