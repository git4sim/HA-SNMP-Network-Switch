"""SNMP Switch DataUpdateCoordinator."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .snmp_client import SNMPSwitchClient

_LOGGER = logging.getLogger(__name__)


class SNMPSwitchCoordinator(DataUpdateCoordinator):
    """Koordiniert SNMP-Datenabrufe für einen Switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SNMPSwitchClient,
        name: str,
        scan_interval: int,
    ) -> None:
        """Initialisierung."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"SNMP Switch {name}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.device_name = name
        self._has_write_access: bool | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Daten vom Switch abrufen."""
        try:
            system_info = await self.client.get_system_info()
            interfaces = await self.client.get_interfaces()

            if system_info.get("description") is None:
                raise UpdateFailed(f"Keine Verbindung zu {self.client.host}")

            return {
                "system": system_info,
                "interfaces": interfaces,
            }
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Fehler beim Abrufen der SNMP-Daten: {err}") from err

    @property
    def has_write_access(self) -> bool:
        """Ob Write-Zugriff konfiguriert ist (Community oder SNMPv3)."""
        return self.client.has_write_access

    def get_interface(self, if_index: int) -> dict[str, Any] | None:
        """Interface-Daten nach Index abrufen."""
        if self.data and "interfaces" in self.data:
            return self.data["interfaces"].get(if_index)
        return None

    def get_system_value(self, key: str) -> Any:
        """Systemwert abrufen."""
        if self.data and "system" in self.data:
            return self.data["system"].get(key)
        return None
