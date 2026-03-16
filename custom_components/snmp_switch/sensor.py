"""Sensors for SNMP Network Switch."""
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
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    IF_ADMIN_STATUS_MAP,
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
    """Set up sensors."""
    coordinator: SNMPSwitchCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # System sensors
    entities.extend([
        SNMPSystemSensor(coordinator, entry, "description", "sys_description", "mdi:information-outline"),
        SNMPUptimeSensor(coordinator, entry),
        SNMPSystemSensor(coordinator, entry, "contact", "sys_contact", "mdi:account"),
        SNMPSystemSensor(coordinator, entry, "name", "sys_name", "mdi:tag-outline"),
        SNMPSystemSensor(coordinator, entry, "location", "sys_location", "mdi:map-marker"),
        SNMPPortCountSensor(coordinator, entry),
    ])

    # Interface sensors (per port)
    if coordinator.data and "interfaces" in coordinator.data:
        for if_index in coordinator.data["interfaces"]:
            entities.extend([
                SNMPInterfaceStatusSensor(coordinator, entry, if_index),
                SNMPPortAdminStatusSensor(coordinator, entry, if_index),
                SNMPInterfaceTrafficSensor(coordinator, entry, if_index, "in"),
                SNMPInterfaceTrafficSensor(coordinator, entry, if_index, "out"),
                SNMPPortErrorSensor(coordinator, entry, if_index, "in"),
                SNMPPortErrorSensor(coordinator, entry, if_index, "out"),
                SNMPPortDescriptionSensor(coordinator, entry, if_index),
                SNMPPortSpeedSensor(coordinator, entry, if_index),
                SNMPPortMacSensor(coordinator, entry, if_index),
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


def _port_label(coordinator: SNMPSwitchCoordinator, if_index: int) -> str:
    iface = coordinator.get_interface(if_index) or {}
    label = iface.get("name") or iface.get("description")
    if label:
        if label.isdigit():
            return f"Port {label}"
        return label
    return f"Port {if_index}"


class SNMPBaseSensor(CoordinatorEntity[SNMPSwitchCoordinator], SensorEntity):
    """Base sensor with entity name translation support."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = _device_info(entry)


# ── System Sensors ──────────────────────────────────────────────────────────

class SNMPSystemSensor(SNMPBaseSensor):
    """Sensor for system info values (sysDescr, sysContact, sysName, sysLocation)."""

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        key: str,
        translation_key: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_sys_{key}"
        self._attr_icon = icon
        self._attr_state_class = None

    @property
    def native_value(self) -> str | None:
        return self.coordinator.get_system_value(self._key)


class SNMPUptimeSensor(SNMPBaseSensor):
    """Sensor for switch uptime."""

    _attr_translation_key = "sys_uptime"

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_sys_uptime"
        self._attr_icon = "mdi:clock-outline"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitOfTime.SECONDS

    @property
    def native_value(self) -> float | None:
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
    """Sensor for port count."""

    _attr_translation_key = "port_count"

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
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
        attrs: dict[str, Any] = {}
        if self.coordinator.data and "interfaces" in self.coordinator.data:
            interfaces = self.coordinator.data["interfaces"]
            up_count = sum(1 for i in interfaces.values() if i.get("oper_status") == 1)
            attrs["ports_up"] = up_count
            attrs["ports_down"] = len(interfaces) - up_count
        return attrs


# ── Port Status Sensors ──────────────────────────────────────────────────────

class SNMPInterfaceStatusSensor(SNMPBaseSensor):
    """Port operational status (ifOperStatus: up/down/dormant...)."""

    _attr_translation_key = "port_status"

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry, if_index: int) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_status"
        self._attr_icon = "mdi:ethernet"
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def native_value(self) -> str | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            return IF_OPER_STATUS_MAP.get(iface.get("oper_status", 2), "unknown")
        return None

    @property
    def icon(self) -> str:
        iface = self.coordinator.get_interface(self._if_index)
        if iface and iface.get("oper_status") == 1:
            return "mdi:ethernet"
        return "mdi:ethernet-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        iface = self.coordinator.get_interface(self._if_index)
        if not iface:
            return {}
        return {
            "if_index": self._if_index,
            "description": iface.get("description", ""),
            "name": iface.get("name", ""),
            "alias": iface.get("alias", ""),
            "mac": iface.get("mac", ""),
            "speed": format_speed(iface.get("speed_mbps", 0)),
            "admin_status": IF_ADMIN_STATUS_MAP.get(iface.get("admin_status", 2), "unknown"),
        }


class SNMPPortAdminStatusSensor(SNMPBaseSensor):
    """Port admin status (ifAdminStatus: up/down/testing)."""

    _attr_translation_key = "port_admin_status"

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry, if_index: int) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_admin_status"
        self._attr_icon = "mdi:ethernet-cable"
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def native_value(self) -> str | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            return IF_ADMIN_STATUS_MAP.get(iface.get("admin_status", 2), "unknown")
        return None

    @property
    def icon(self) -> str:
        iface = self.coordinator.get_interface(self._if_index)
        if iface and iface.get("admin_status") == 1:
            return "mdi:ethernet-cable"
        return "mdi:ethernet-cable-off"


# ── Port Traffic ─────────────────────────────────────────────────────────────

class SNMPInterfaceTrafficSensor(SNMPBaseSensor):
    """Sensor for port traffic (RX/TX bytes, HC counters preferred)."""

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        if_index: int,
        direction: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        self._direction = direction
        self._attr_translation_key = "port_rx" if direction == "in" else "port_tx"
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_{direction}_octets"
        self._attr_icon = "mdi:transfer-down" if direction == "in" else "mdi:transfer-up"
        self._attr_native_unit_of_measurement = "B"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_device_class = SensorDeviceClass.DATA_SIZE
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def native_value(self) -> int | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            key = "in_octets" if self._direction == "in" else "out_octets"
            return iface.get(key)
        return None


# ── Port Errors ──────────────────────────────────────────────────────────────

class SNMPPortErrorSensor(SNMPBaseSensor):
    """Sensor for port errors (split by RX/TX)."""

    def __init__(
        self,
        coordinator: SNMPSwitchCoordinator,
        entry: ConfigEntry,
        if_index: int,
        direction: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        self._direction = direction
        self._attr_translation_key = "port_rx_errors" if direction == "in" else "port_tx_errors"
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_{direction}_errors"
        self._attr_icon = "mdi:alert-circle-outline"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def native_value(self) -> int | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            key = "in_errors" if self._direction == "in" else "out_errors"
            return iface.get(key, 0)
        return None


# ── Port Diagnostics ────────────────────────────────────────────────────────

class SNMPPortDescriptionSensor(SNMPBaseSensor):
    """Sensor for port description (ifDescr — hardware name)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "port_description"

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry, if_index: int) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_description"
        self._attr_icon = "mdi:information-outline"
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def native_value(self) -> str | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            return iface.get("description") or iface.get("name")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        iface = self.coordinator.get_interface(self._if_index)
        if not iface:
            return {}
        return {
            "if_index": self._if_index,
            "if_name": iface.get("name", ""),
            "if_descr": iface.get("description", ""),
            "alias": iface.get("alias", ""),
        }


class SNMPPortSpeedSensor(SNMPBaseSensor):
    """Sensor for port speed (ifHighSpeed in Mbit/s)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "port_speed"

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry, if_index: int) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_speed"
        self._attr_icon = "mdi:speedometer"
        self._attr_native_unit_of_measurement = "Mbit/s"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def native_value(self) -> int | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            speed = iface.get("speed_mbps", 0)
            return speed if speed else None
        return None


class SNMPPortMacSensor(SNMPBaseSensor):
    """Sensor for port MAC address (ifPhysAddress)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "port_mac"

    def __init__(self, coordinator: SNMPSwitchCoordinator, entry: ConfigEntry, if_index: int) -> None:
        super().__init__(coordinator, entry)
        self._if_index = if_index
        self._attr_unique_id = f"{entry.entry_id}_if_{if_index}_mac"
        self._attr_icon = "mdi:identifier"
        self._attr_translation_placeholders = {"port_name": _port_label(coordinator, if_index)}

    @property
    def native_value(self) -> str | None:
        iface = self.coordinator.get_interface(self._if_index)
        if iface:
            mac = iface.get("mac", "")
            return mac if mac else None
        return None
