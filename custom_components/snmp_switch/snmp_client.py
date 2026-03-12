"""SNMP Client — pysnmp 6.x (lextudio) compatible, no blocking calls."""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# ── Import pysnmp core — done at module level but snmp_client.py itself
#    is only imported lazily (inside _make_client) so this never runs
#    during package init before requirements are installed.

# Import everything from the single compat layer — mixing modules causes
# SnmpEngine version mismatches (getUserContext errors).
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    nextCmd,
    setCmd,
)
from pysnmp.proto.rfc1902 import Integer, OctetString

# ── Auth / Priv protocol objects ──────────────────────────────────────────
# pysnmp 6.x re-exports these from hlapi.v3arch.asyncio.
# Use direct try/except — no importlib (which would block the event loop).

from pysnmp.hlapi.asyncio import usmNoAuthProtocol, usmNoPrivProtocol

try:
    from pysnmp.hlapi.asyncio import usmHMACSHAAuthProtocol
except ImportError:
    usmHMACSHAAuthProtocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usmHMAC128SHA224AuthProtocol
except ImportError:
    usmHMAC128SHA224AuthProtocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usmHMAC192SHA256AuthProtocol
except ImportError:
    usmHMAC192SHA256AuthProtocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usmHMAC256SHA384AuthProtocol
except ImportError:
    usmHMAC256SHA384AuthProtocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usmHMAC384SHA512AuthProtocol
except ImportError:
    usmHMAC384SHA512AuthProtocol = None  # type: ignore[assignment]

try:  # MD5 removed in pysnmp 6.x (deprecated)
    from pysnmp.hlapi.asyncio import usmHMACMD5AuthProtocol
except ImportError:
    usmHMACMD5AuthProtocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usmDESPrivProtocol
except ImportError:
    usmDESPrivProtocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usm3DESEDEPrivProtocol
except ImportError:
    usm3DESEDEPrivProtocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usmAesCfb128Protocol
except ImportError:
    usmAesCfb128Protocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usmAesCfb192Protocol
except ImportError:
    usmAesCfb192Protocol = None  # type: ignore[assignment]

try:
    from pysnmp.hlapi.asyncio import usmAesCfb256Protocol
except ImportError:
    usmAesCfb256Protocol = None  # type: ignore[assignment]

from .const import (
    SNMP_VERSION_1,
    SNMP_VERSION_3,
    V3_AUTH_MD5,
    V3_AUTH_NONE,
    V3_AUTH_SHA,
    V3_AUTH_SHA224,
    V3_AUTH_SHA256,
    V3_AUTH_SHA384,
    V3_AUTH_SHA512,
    V3_PRIV_3DES,
    V3_PRIV_AES128,
    V3_PRIV_AES192,
    V3_PRIV_AES256,
    V3_PRIV_DES,
    V3_PRIV_NONE,
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

_AUTH_PROTO_MAP: dict[str, Any] = {
    V3_AUTH_NONE:   usmNoAuthProtocol,
    V3_AUTH_MD5:    usmHMACMD5AuthProtocol,
    V3_AUTH_SHA:    usmHMACSHAAuthProtocol,
    V3_AUTH_SHA224: usmHMAC128SHA224AuthProtocol,
    V3_AUTH_SHA256: usmHMAC192SHA256AuthProtocol,
    V3_AUTH_SHA384: usmHMAC256SHA384AuthProtocol,
    V3_AUTH_SHA512: usmHMAC384SHA512AuthProtocol,
}

_PRIV_PROTO_MAP: dict[str, Any] = {
    V3_PRIV_NONE:   usmNoPrivProtocol,
    V3_PRIV_DES:    usmDESPrivProtocol,
    V3_PRIV_3DES:   usm3DESEDEPrivProtocol,
    V3_PRIV_AES128: usmAesCfb128Protocol,
    V3_PRIV_AES192: usmAesCfb192Protocol,
    V3_PRIV_AES256: usmAesCfb256Protocol,
}

# Log which protocols are unavailable in this pysnmp version
for _k, _v in {**_AUTH_PROTO_MAP, **_PRIV_PROTO_MAP}.items():
    if _v is None and _k != V3_AUTH_MD5:  # MD5 removal is expected, don't spam
        _LOGGER.warning(
            "snmp_switch: protocol '%s' not available in this pysnmp version", _k
        )


# ── Shared SnmpEngine — created once in executor to avoid blocking the loop ──
# SnmpEngine() reads MIB files from disk on init (blocking I/O).
# We create it once at module level but defer it to an executor call.
_ENGINE: SnmpEngine | None = None


def _get_or_create_engine() -> SnmpEngine:
    """Return the shared SnmpEngine, creating it if needed (call in executor)."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = SnmpEngine()
    return _ENGINE


class SNMPSwitchClient:
    """Async SNMP client — pysnmp 6.x, no blocking event-loop calls."""

    def __init__(
        self,
        host: str,
        port: int,
        community_read: str = "public",
        community_write: str | None = None,
        snmp_version: str = "2c",
        v3_username: str = "",
        v3_auth_protocol: str = V3_AUTH_NONE,
        v3_auth_key: str = "",
        v3_priv_protocol: str = V3_PRIV_NONE,
        v3_priv_key: str = "",
        v3_context_name: str = "",
        timeout: int = 5,
        retries: int = 1,
    ) -> None:
        self.host = host
        self.port = port
        self.community_read = community_read
        self.community_write = community_write
        self.snmp_version = snmp_version
        self.v3_username = v3_username
        self.v3_auth_protocol = v3_auth_protocol
        self.v3_auth_key = v3_auth_key
        self.v3_priv_protocol = v3_priv_protocol
        self.v3_priv_key = v3_priv_key
        self.v3_context_name = v3_context_name
        self.timeout = timeout
        self.retries = retries
        # Engine is NOT created here — use _engine() async property instead

    async def _engine(self) -> SnmpEngine:
        """Return shared SnmpEngine, initialising it in an executor if needed."""
        import asyncio
        if _ENGINE is None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _get_or_create_engine)
        return _ENGINE  # type: ignore[return-value]

    def _mp_model(self) -> int:
        return 0 if self.snmp_version == SNMP_VERSION_1 else 1

    def _read_auth(self) -> CommunityData | UsmUserData:
        if self.snmp_version == SNMP_VERSION_3:
            return self._usm_user()
        return CommunityData(self.community_read, mpModel=self._mp_model())

    def _write_auth(self) -> CommunityData | UsmUserData:
        if self.snmp_version == SNMP_VERSION_3:
            return self._usm_user()
        return CommunityData(
            self.community_write or self.community_read, mpModel=self._mp_model()
        )

    def _usm_user(self) -> UsmUserData:
        auth_proto = _AUTH_PROTO_MAP.get(self.v3_auth_protocol, usmNoAuthProtocol)
        priv_proto = _PRIV_PROTO_MAP.get(self.v3_priv_protocol, usmNoPrivProtocol)
        has_auth = self.v3_auth_protocol != V3_AUTH_NONE and bool(self.v3_auth_key)
        has_priv = self.v3_priv_protocol != V3_PRIV_NONE and bool(self.v3_priv_key)

        if has_auth and has_priv:
            return UsmUserData(
                self.v3_username,
                authKey=self.v3_auth_key,
                privKey=self.v3_priv_key,
                authProtocol=auth_proto,
                privProtocol=priv_proto,
            )
        if has_auth:
            return UsmUserData(
                self.v3_username,
                authKey=self.v3_auth_key,
                authProtocol=auth_proto,
            )
        return UsmUserData(self.v3_username)

    def _context(self) -> ContextData:
        return ContextData()

    async def _transport(self) -> UdpTransportTarget:
        # pysnmp 6.x: UdpTransportTarget.create() exists but _resolve_address
        # raises NotImplementedError for the base class when host is a string.
        # The correct approach in 6.x is the sync constructor with a pre-resolved
        # (host, port) tuple — DNS resolution must happen in an executor.
        import asyncio
        import socket

        loop = asyncio.get_event_loop()
        # Resolve hostname to IP in executor (blocking DNS lookup)
        try:
            infos = await loop.run_in_executor(
                None,
                lambda: socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_DGRAM)
            )
            ip = infos[0][4][0]
        except Exception:
            ip = self.host  # fallback: hope it's already an IP

        # UdpTransportTarget._resolve_address() is abstract in the base class and
        # raises NotImplementedError. Since we already resolved ip above, subclass
        # it to return the address directly so create() doesn't try async DNS lookup.
        class _PreResolvedUdpTransport(UdpTransportTarget):
            async def _resolve_address(self, addr):  # type: ignore[override]
                return addr

        return await _PreResolvedUdpTransport.create((ip, self.port), timeout=self.timeout, retries=self.retries)

    @property
    def security_level(self) -> str:
        if self.snmp_version != SNMP_VERSION_3:
            return f"community ({self.snmp_version})"
        has_auth = self.v3_auth_protocol != V3_AUTH_NONE and bool(self.v3_auth_key)
        has_priv = self.v3_priv_protocol != V3_PRIV_NONE and bool(self.v3_priv_key)
        if has_auth and has_priv:
            return f"authPriv ({self.v3_auth_protocol}/{self.v3_priv_protocol})"
        if has_auth:
            return f"authNoPriv ({self.v3_auth_protocol})"
        return "noAuthNoPriv"

    @property
    def has_write_access(self) -> bool:
        if self.snmp_version == SNMP_VERSION_3:
            return bool(self.v3_username)
        return bool(self.community_write)

    # ── Core SNMP operations ─────────────────────────────────────────────────

    async def get(self, oid: str) -> str | None:
        try:
            engine = await self._engine()
            transport = await self._transport()
            errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
                engine, self._read_auth(), transport, self._context(),
                ObjectType(ObjectIdentity(oid)),
            )
            if errorIndication:
                _LOGGER.warning("GET error [%s] %s: %s", self.host, oid, errorIndication)
                return None
            if errorStatus:
                _LOGGER.warning("GET status [%s] %s: %s", self.host, oid, errorStatus.prettyPrint())
                return None
            for varBind in varBinds:
                return varBind[1].prettyPrint()
        except Exception as err:
            _LOGGER.error("GET exception [%s] %s: %s: %r", self.host, oid, type(err).__name__, err, exc_info=True)
        return None

    async def get_raw(self, oid: str) -> int | str | None:
        try:
            engine = await self._engine()
            transport = await self._transport()
            errorIndication, errorStatus, errorIndex, varBinds = await getCmd(
                engine, self._read_auth(), transport, self._context(),
                ObjectType(ObjectIdentity(oid)),
            )
            if errorIndication or errorStatus:
                return None
            for varBind in varBinds:
                try:
                    return int(varBind[1])
                except (ValueError, TypeError):
                    return str(varBind[1])
        except Exception as err:
            _LOGGER.error("GET_RAW exception [%s] %s: %s: %r", self.host, oid, type(err).__name__, err, exc_info=True)
        return None

    async def walk(self, oid: str) -> dict[str, str]:
        results: dict[str, str] = {}
        try:
            engine = await self._engine()
            transport = await self._transport()
            async for errorIndication, errorStatus, errorIndex, varBinds in nextCmd(
                engine, self._read_auth(), transport, self._context(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False,
            ):
                if errorIndication:
                    _LOGGER.warning("WALK error [%s] %s: %s", self.host, oid, errorIndication)
                    break
                if errorStatus:
                    _LOGGER.warning("WALK status [%s] %s: %s", self.host, oid, errorStatus.prettyPrint())
                    break
                for varBind in varBinds:
                    results[str(varBind[0])] = varBind[1].prettyPrint()
        except Exception as err:
            _LOGGER.error("WALK exception [%s] %s: %s: %r", self.host, oid, type(err).__name__, err, exc_info=True)
        return results

    async def set_string(self, oid: str, value: str) -> bool:
        if not self.has_write_access:
            _LOGGER.warning("No write access — SET skipped for %s", oid)
            return False
        try:
            engine = await self._engine()
            transport = await self._transport()
            errorIndication, errorStatus, errorIndex, varBinds = await setCmd(
                engine, self._write_auth(), transport, self._context(),
                ObjectType(ObjectIdentity(oid), OctetString(value)),
            )
            if errorIndication:
                _LOGGER.error("SET string error [%s] %s: %s", self.host, oid, errorIndication)
                return False
            if errorStatus:
                _LOGGER.error("SET string status [%s] %s: %s", self.host, oid, errorStatus.prettyPrint())
                return False
            return True
        except Exception as err:
            _LOGGER.error("SET string exception [%s] %s: %s: %r", self.host, oid, type(err).__name__, err, exc_info=True)
            return False

    async def set_integer(self, oid: str, value: int) -> bool:
        if not self.has_write_access:
            _LOGGER.warning("No write access — SET skipped for %s", oid)
            return False
        try:
            engine = await self._engine()
            transport = await self._transport()
            errorIndication, errorStatus, errorIndex, varBinds = await setCmd(
                engine, self._write_auth(), transport, self._context(),
                ObjectType(ObjectIdentity(oid), Integer(value)),
            )
            if errorIndication:
                _LOGGER.error("SET int error [%s] %s: %s", self.host, oid, errorIndication)
                return False
            if errorStatus:
                _LOGGER.error("SET int status [%s] %s: %s", self.host, oid, errorStatus.prettyPrint())
                return False
            return True
        except Exception as err:
            _LOGGER.error("SET int exception [%s] %s: %s: %r", self.host, oid, type(err).__name__, err, exc_info=True)
            return False

    # ── High-level helpers ───────────────────────────────────────────────────

    async def test_connection(self) -> bool:
        return (await self.get(OID_SYS_DESCR)) is not None

    async def get_system_info(self) -> dict[str, Any]:
        return {
            "description": await self.get(OID_SYS_DESCR),
            "uptime_raw":  await self.get_raw(OID_SYS_UPTIME),
            "contact":     await self.get(OID_SYS_CONTACT),
            "name":        await self.get(OID_SYS_NAME),
            "location":    await self.get(OID_SYS_LOCATION),
            "if_number":   await self.get_raw(OID_IF_NUMBER),
        }

    async def get_interfaces(self) -> dict[int, dict[str, Any]]:
        descs          = await self.walk(OID_IF_DESCR)
        admin_statuses = await self.walk(OID_IF_ADMIN_STATUS)
        oper_statuses  = await self.walk(OID_IF_OPER_STATUS)
        macs           = await self.walk(OID_IF_PHYS_ADDRESS)
        in_octets      = await self.walk(OID_IF_IN_OCTETS)
        out_octets     = await self.walk(OID_IF_OUT_OCTETS)
        in_errors      = await self.walk(OID_IF_IN_ERRORS)
        out_errors     = await self.walk(OID_IF_OUT_ERRORS)
        names          = await self.walk(OID_IF_NAME)
        speeds         = await self.walk(OID_IF_HIGH_SPEED)
        aliases        = await self.walk(OID_IF_ALIAS)
        hc_in          = await self.walk(OID_IF_HC_IN_OCTETS)
        hc_out         = await self.walk(OID_IF_HC_OUT_OCTETS)

        def _idx(d: dict) -> dict[int, str]:
            result: dict[int, str] = {}
            for oid, val in d.items():
                try:
                    result[int(oid.split(".")[-1])] = val
                except (ValueError, IndexError):
                    pass
            return result

        desc_m   = _idx(descs)
        admin_m  = _idx(admin_statuses)
        oper_m   = _idx(oper_statuses)
        mac_m    = _idx(macs)
        in_m     = _idx(in_octets)
        out_m    = _idx(out_octets)
        in_e_m   = _idx(in_errors)
        out_e_m  = _idx(out_errors)
        name_m   = _idx(names)
        speed_m  = _idx(speeds)
        alias_m  = _idx(aliases)
        hc_in_m  = _idx(hc_in)
        hc_out_m = _idx(hc_out)

        interfaces: dict[int, dict[str, Any]] = {}
        for idx in desc_m:
            try:
                admin_val  = int(admin_m.get(idx, 2))
                oper_val   = int(oper_m.get(idx, 2))
                speed_mbps = int(speed_m.get(idx, 0))
            except (ValueError, TypeError):
                admin_val, oper_val, speed_mbps = 2, 2, 0

            interfaces[idx] = {
                "index":        idx,
                "description":  desc_m.get(idx, f"Port {idx}"),
                "name":         name_m.get(idx, f"if{idx}"),
                "alias":        alias_m.get(idx, ""),
                "admin_status": admin_val,
                "oper_status":  oper_val,
                "mac":          mac_m.get(idx, ""),
                "speed_mbps":   speed_mbps,
                "in_octets":    int(hc_in_m.get(idx, in_m.get(idx, 0)) or 0),
                "out_octets":   int(hc_out_m.get(idx, out_m.get(idx, 0)) or 0),
                "in_errors":    int(in_e_m.get(idx, 0) or 0),
                "out_errors":   int(out_e_m.get(idx, 0) or 0),
            }
        return interfaces

    async def set_port_admin_status(self, if_index: int, enable: bool) -> bool:
        return await self.set_integer(f"{OID_IF_ADMIN_STATUS}.{if_index}", 1 if enable else 2)

    async def set_port_alias(self, if_index: int, alias: str) -> bool:
        return await self.set_string(f"{OID_IF_ALIAS}.{if_index}", alias)

    async def set_sys_contact(self, contact: str) -> bool:
        return await self.set_string(OID_SYS_CONTACT, contact)

    async def set_sys_name(self, name: str) -> bool:
        return await self.set_string(OID_SYS_NAME, name)

    async def set_sys_location(self, location: str) -> bool:
        return await self.set_string(OID_SYS_LOCATION, location)
