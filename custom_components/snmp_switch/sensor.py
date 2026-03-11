"""Sensoren für SNMP Network Switch."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, UnitOfDataRate, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_COMMUNITY_WRITE,
    DOMAIN,
    IF_OPER_STATUS_MAP,
    format_speed,
)
from .coordinator import SNMPSwitchCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren einrichten."""
    coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = {**entry.data, **entry.options}

    entities: list[SensorEntity] = []

    # System-Sensoren
    entities.extend([
        SNMPSystemSensor(coordinator, entry, "description", "Beschreibung", "mdi:information-outline"),
        SNMPUptimeSensor(coordinator, entry),
        SNMPSystemSensor(coordinator, entry, "contact", "Kontakt", "mdi:account"),
        SNMPSystemSensor(coordinator, entry, "name", "Systemname", "mdi:tag-outline"),
        SNMPSystemSensor(coordinator, entry, "location", "Standort", "mdi:map-marker"),
        SNMPPortCountSensor(coordinator, entry),
    ])

    # Interface-Sensoren (pro Port)
    if coordinator.data and "interfaces" in coordinator.data:
        for if_index, iface in coordinator.data["interfaces"].items():
            entities.extend([
                SNMPInterfaceStatusSensor(coordinator, entry, if_index),
                SNMPInterfaceTrafficSensor(coordinator, entry, if_index, "in"),
                SNMPInterfaceTrafficSensor(coordinator, entry, if_index, "out"),
                SNMPInterfaceErrorSensor(coordinator, entry, if_index),
            ])

    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    data = entry.data
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=data.get(CONF_NAME) or data[CONF_HOST],
        manufacturer="Network Switch",
        model="SNMP Managed Switch",
        sw_version=None,
        configuration_url=f"http://{data[CONF_HOST]}",
    )


class SNMPBaseSensor(CoordinatorEntity[SNMPSwitchCoordinator], SensorEntity):
    """Basis-Sensor."""

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device_info(entry)

    @property
    def has_write_access(self) -> bool:
        return bool(self._entry.data.get(CONF_COMMUNITY_WRITE) or self._entry.options.get(CONF_COMMUNITY_WRITE))


class SNMPSystemSensor(SNMPBaseSensor):
    """Sensor für Systeminfo-Werte."""

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._attr_name = f"{entry.data.get(CONF_NAME) or entry.data[CONF_HOST]} {name}"
        self._attr_unique_id = f"{entry.entry_id}_sys_{key}"
        self._attr_icon = icon
        self._attr_state_class = None

    @property
    def native_value(self) -> str | None:
        return self.coordinator.get_system_value(self._key)


class SNMPUptimeSensor(SNMPBaseSensor):
    """Sensor für Switch-Uptime."""

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        host = entry.data.get(CONF_NAME) or entry.data[CONF_HOST]
        self._attr_name = f"{host} Uptime"
        self._attr_unique_id = f"{entry.entry_id}_sys_uptime"
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS

    @property
    def native_value(self) -> float | None:
        """Uptime in Sekunden (sysUpTime ist in 1/100 Sek)."""
        raw = self.coordinator.get_system_value("uptime_raw")
        if raw is not None:
            try:
                return round(int(raw) / 100)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        raw = self.coordinator.get_system_value("uptime_raw")
        if raw is not None:
            try:
                seconds = int(raw) // 100
                days = seconds // 86400
                hours = (seconds % 86400) // 3600
                minutes = (seconds % 3600) // 60
                return {"uptime_human": f"{days}d {hours:02d}h {minutes:02d}m"}
            except (ValueError, TypeError):
                pass
        return {}


class SNMPPortCountSensor(SNMPBaseSensor):
    """Sensor für Anzahl der Ports."""

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        host = entry.data.get(CONF_NAME) or entry.data[CONF_HOST]
        self._attr_name = f"{host} Anzahl Ports"
        self._attr_unique_id = f"{entry.entry_id}_sys_if_number"
        self._attr_icon = "mdi:ethernet"
        self._attr_native_unit_of_measurement = "Ports"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        val = self.coordinator.get_system_value("if_number")
        try:
            return int(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Übersicht aller Ports."""
        attrs: dict[str, Any] = {}
        if self.coordinator.data and "interfaces" in self.coordinator.data:
            interfaces = self.coordinator.data["interfaces"]
            up_count = sum(1 for i in interfaces.values() if i.get("oper_status") == 1)
            attrs["ports_up"] = up_count
            attrs["ports_down"] = len(interfaces) - up_count
        return attrs


class SNMPInterfaceStatusSensor(SNMPBaseSensor):
    """Sensor für Port-Status."""

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        if_index: int,
    ) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        host = entry.data.get(CONF_NAME) or entry.data[CONF_HOST]
        iface = coordinator.get_interface(if_index) or {}
        port_name = iface.get("name") or iface.get("description") or f"Port {if_index}"
        self._attr_name = f"{host} {port_name} Status"
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_status"
        self._attr_icon = "mdi:ethernet"

    @property
    def native_value(self) -> str | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            oper = iface.get("oper_status", 2)
            return IF_OPER_STATUS_MAP.get(oper, "unknown")
        return None

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
            "admin_status": "up" if iface.get("admin_status") == 1 else "down",
            "oper_status": IF_OPER_STATUS_MAP.get(iface.get("oper_status", 2), "unknown"),
        }

    @property
    def icon(self) -> str:
        iface = self.coordinator.get_interface(self._if_index)
        if iface and iface.get("oper_status") == 1:
            return "mdi:ethernet"
        return "mdi:ethernet-off"


class SNMPInterfaceTrafficSensor(SNMPBaseSensor):
    """Sensor für Port-Traffic (In/Out Bytes)."""

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        if_index: int,
        direction: str,  # "in" oder "out"
    ) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        self._direction = direction
        host = entry.data.get(CONF_NAME) or entry.data[CONF_HOST]
        iface = coordinator.get_interface(if_index) or {}
        port_name = iface.get("name") or iface.get("description") or f"Port {if_index}"
        dir_label = "RX" if direction == "in" else "TX"
        self._attr_name = f"{host} {port_name} {dir_label}"
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_{direction}_octets"
        self._attr_icon = "mdi:transfer-down" if direction == "in" else "mdi:transfer-up"
        self._attr_native_unit_of_measurement = "B"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_class = SensorDeviceClass.DATA_SIZE

    @property
    def native_value(self) -> int | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            key = "in_octets" if self._direction == "in" else "out_octets"
            return iface.get(key)
        return None


class SNMPInterfaceErrorSensor(SNMPBaseSensor):
    """Sensor für Port-Fehler."""

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        if_index: int,
    ) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        host = entry.data.get(CONF_NAME) or entry.data[CONF_HOST]
        iface = coordinator.get_interface(if_index) or {}
        port_name = iface.get("name") or iface.get("description") or f"Port {if_index}"
        self._attr_name = f"{host} {port_name} Fehler"
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_errors"
        self._attr_icon = "mdi:alert-circle-outline"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> int | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            return (iface.get("in_errors", 0) or 0) + (iface.get("out_errors", 0) or 0)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        iface = self.coordinator.get_interface(self._if_index)
        if not iface:
            return {}
        return {
            "in_errors": iface.get("in_errors", 0),
            "out_errors": iface.get("out_errors", 0),
        }
