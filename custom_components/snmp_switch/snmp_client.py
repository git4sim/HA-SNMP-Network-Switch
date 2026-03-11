"""SNMP Client für Netzwerkswitches."""
from __future__ import annotations

import logging
from typing import Any

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    bulkCmd,
    getCmd,
    nextCmd,
    setCmd,
)
from pysnmp.proto.rfc1902 import Integer, OctetString

from .const import (
    SNMP_VERSION_1,
    SNMP_VERSION_2C,
    OID_IF_ADMIN_STATUS,
    OID_IF_ALIAS,
    OID_IF_DESCR,
    OID_IF_HC_IN_OCTETS,
    OID_IF_HC_OUT_OCTETS,
    OID_IF_HIGH_SPEED,
    OID_IF_IN_ERRORS,
    OID_IF_IN_OCTETS,
    OID_IF_NAME,
    OID_IF_NUMBER,
    OID_IF_OPER_STATUS,
    OID_IF_OUT_ERRORS,
    OID_IF_OUT_OCTETS,
    OID_IF_PHYS_ADDRESS,
    OID_SYS_CONTACT,
    OID_SYS_DESCR,
    OID_SYS_LOCATION,
    OID_SYS_NAME,
    OID_SYS_UPTIME,
)

_LOGGER = logging.getLogger(__name__)


class SNMPSwitchClient:
    """SNMP Client für Netzwerkswitches."""

    def __init__(
        self,
        host: str,
        port: int,
        community_read: str,
        community_write: str | None = None,
        snmp_version: str = SNMP_VERSION_2C,
        timeout: int = 5,
        retries: int = 1,
    ) -> None:
        """Initialisierung."""
        self.host = host
        self.port = port
        self.community_read = community_read
        self.community_write = community_write
        self.snmp_version = snmp_version
        self.timeout = timeout
        self.retries = retries
        self._engine = SnmpEngine()

    def _get_mp_model(self) -> int:
        """SNMP MP Model: 0=v1, 1=v2c."""
        return 0 if self.snmp_version == SNMP_VERSION_1 else 1

    def _read_community(self) -> CommunityData:
        return CommunityData(self.community_read, mpModel=self._get_mp_model())

    def _write_community(self) -> CommunityData:
        community = self.community_write or self.community_read
        return CommunityData(community, mpModel=self._get_mp_model())

    async def _transport(self) -> UdpTransportTarget:
        return await UdpTransportTarget.create(
            (self.host, self.port),
            timeout=self.timeout,
            retries=self.retries,
        )

    async def get(self, oid: str) -> Any:
        """Einzelnen OID-Wert abrufen."""
        try:
            transport = await self._transport()
            errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
                self._engine,
                self._read_community(),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
            if errorIndication:
                _LOGGER.warning("SNMP GET Fehler für %s: %s", oid, errorIndication)
                return None
            if errorStatus:
                _LOGGER.warning("SNMP GET Status-Fehler für %s: %s", oid, errorStatus.prettyPrint())
                return None
            for varBind in varBinds:
                return varBind[1].prettyPrint()
        except Exception as err:
            _LOGGER.error("SNMP GET Exception für %s@%s: %s", oid, self.host, err)
            return None

    async def get_raw(self, oid: str) -> Any:
        """Rohen OID-Wert als Integer abrufen."""
        try:
            transport = await self._transport()
            errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
                self._engine,
                self._read_community(),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
            if errorIndication or errorStatus:
                return None
            for varBind in varBinds:
                val = varBind[1]
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return str(val)
        except Exception as err:
            _LOGGER.error("SNMP GET RAW Exception: %s", err)
            return None

    async def walk(self, oid: str) -> dict[str, Any]:
        """OID-Tabelle abrufen (SNMP WALK)."""
        results = {}
        try:
            transport = await self._transport()
            async for errorIndication, errorStatus, errorIndex, varBinds in nextCmd(
                self._engine,
                self._read_community(),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
            ):
                if errorIndication:
                    _LOGGER.warning("SNMP WALK Fehler für %s: %s", oid, errorIndication)
                    break
                if errorStatus:
                    _LOGGER.warning("SNMP WALK Status-Fehler: %s", errorStatus.prettyPrint())
                    break
                for varBind in varBinds:
                    key = str(varBind[0])
                    value = varBind[1].prettyPrint()
                    results[key] = value
        except Exception as err:
            _LOGGER.error("SNMP WALK Exception für %s@%s: %s", oid, self.host, err)
        return results

    async def set_string(self, oid: str, value: str) -> bool:
        """OID-Wert als String setzen (benötigt Write-Community)."""
        if not self.community_write:
            _LOGGER.warning("Kein Write-Community konfiguriert, SET nicht möglich")
            return False
        try:
            transport = await self._transport()
            errorIndication, errorStatus, errorIndex, varBinds = await setCmd(
                self._engine,
                self._write_community(),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid), OctetString(value)),
            )
            if errorIndication:
                _LOGGER.error("SNMP SET Fehler: %s", errorIndication)
                return False
            if errorStatus:
                _LOGGER.error("SNMP SET Status-Fehler: %s", errorStatus.prettyPrint())
                return False
            return True
        except Exception as err:
            _LOGGER.error("SNMP SET Exception: %s", err)
            return False

    async def set_integer(self, oid: str, value: int) -> bool:
        """OID-Wert als Integer setzen."""
        if not self.community_write:
            _LOGGER.warning("Kein Write-Community konfiguriert, SET nicht möglich")
            return False
        try:
            transport = await self._transport()
            errorIndication, errorStatus, errorIndex, varBinds = await setCmd(
                self._engine,
                self._write_community(),
                transport,
                ContextData(),
                ObjectType(ObjectIdentity(oid), Integer(value)),
            )
            if errorIndication:
                _LOGGER.error("SNMP SET Integer Fehler: %s", errorIndication)
                return False
            if errorStatus:
                _LOGGER.error("SNMP SET Integer Status-Fehler: %s", errorStatus.prettyPrint())
                return False
            return True
        except Exception as err:
            _LOGGER.error("SNMP SET Integer Exception: %s", err)
            return False

    async def test_connection(self) -> bool:
        """Verbindung zum Switch testen."""
        result = await self.get(OID_SYS_DESCR)
        return result is not None

    async def get_system_info(self) -> dict[str, Any]:
        """Systeminformationen abrufen."""
        return {
            "description": await self.get(OID_SYS_DESCR),
            "uptime_raw": await self.get_raw(OID_SYS_UPTIME),
            "contact": await self.get(OID_SYS_CONTACT),
            "name": await self.get(OID_SYS_NAME),
            "location": await self.get(OID_SYS_LOCATION),
            "if_number": await self.get_raw(OID_IF_NUMBER),
        }

    async def get_interfaces(self) -> dict[int, dict[str, Any]]:
        """Alle Interface-Daten abrufen."""
        interfaces: dict[int, dict[str, Any]] = {}

        # Tabellen parallel abrufen
        descs = await self.walk(OID_IF_DESCR)
        admin_statuses = await self.walk(OID_IF_ADMIN_STATUS)
        oper_statuses = await self.walk(OID_IF_OPER_STATUS)
        macs = await self.walk(OID_IF_PHYS_ADDRESS)
        in_octets = await self.walk(OID_IF_IN_OCTETS)
        out_octets = await self.walk(OID_IF_OUT_OCTETS)
        in_errors = await self.walk(OID_IF_IN_ERRORS)
        out_errors = await self.walk(OID_IF_OUT_ERRORS)
        names = await self.walk(OID_IF_NAME)
        speeds = await self.walk(OID_IF_HIGH_SPEED)
        aliases = await self.walk(OID_IF_ALIAS)
        hc_in = await self.walk(OID_IF_HC_IN_OCTETS)
        hc_out = await self.walk(OID_IF_HC_OUT_OCTETS)

        # Index aus OID extrahieren (letztes Segment)
        def extract_index(oid_dict: dict) -> dict[int, str]:
            result = {}
            for oid, val in oid_dict.items():
                try:
                    idx = int(oid.split(".")[-1])
                    result[idx] = val
                except (ValueError, IndexError):
                    pass
            return result

        desc_map = extract_index(descs)
        admin_map = extract_index(admin_statuses)
        oper_map = extract_index(oper_statuses)
        mac_map = extract_index(macs)
        in_map = extract_index(in_octets)
        out_map = extract_index(out_octets)
        in_err_map = extract_index(in_errors)
        out_err_map = extract_index(out_errors)
        name_map = extract_index(names)
        speed_map = extract_index(speeds)
        alias_map = extract_index(aliases)
        hc_in_map = extract_index(hc_in)
        hc_out_map = extract_index(hc_out)

        for idx in desc_map:
            try:
                admin_val = int(admin_map.get(idx, 2))
                oper_val = int(oper_map.get(idx, 2))
                speed_mbps = int(speed_map.get(idx, 0))
            except (ValueError, TypeError):
                admin_val, oper_val, speed_mbps = 2, 2, 0

            interfaces[idx] = {
                "index": idx,
                "description": desc_map.get(idx, f"Port {idx}"),
                "name": name_map.get(idx, f"if{idx}"),
                "alias": alias_map.get(idx, ""),
                "admin_status": admin_val,
                "oper_status": oper_val,
                "mac": mac_map.get(idx, ""),
                "speed_mbps": speed_mbps,
                "in_octets": int(hc_in_map.get(idx, in_map.get(idx, 0)) or 0),
                "out_octets": int(hc_out_map.get(idx, out_map.get(idx, 0)) or 0),
                "in_errors": int(in_err_map.get(idx, 0) or 0),
                "out_errors": int(out_err_map.get(idx, 0) or 0),
            }

        return interfaces

    async def set_port_admin_status(self, if_index: int, enable: bool) -> bool:
        """Port ein-/ausschalten (ifAdminStatus: 1=up, 2=down)."""
        oid = f"{OID_IF_ADMIN_STATUS}.{if_index}"
        value = 1 if enable else 2
        return await self.set_integer(oid, value)

    async def set_port_alias(self, if_index: int, alias: str) -> bool:
        """Port-Beschreibung (ifAlias) setzen."""
        oid = f"{OID_IF_ALIAS}.{if_index}"
        return await self.set_string(oid, alias)

    async def set_sys_contact(self, contact: str) -> bool:
        """sysContact setzen."""
        return await self.set_string(OID_SYS_CONTACT, contact)

    async def set_sys_name(self, name: str) -> bool:
        """sysName setzen."""
        return await self.set_string(OID_SYS_NAME, name)

    async def set_sys_location(self, location: str) -> bool:
        """sysLocation setzen."""
        return await self.set_string(OID_SYS_LOCATION, location)
