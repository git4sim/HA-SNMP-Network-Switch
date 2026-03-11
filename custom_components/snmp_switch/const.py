"""Constants for the SNMP Network Switch integration."""

DOMAIN = "snmp_switch"
DEFAULT_PORT = 161
DEFAULT_COMMUNITY_READ = "public"
DEFAULT_SCAN_INTERVAL = 30

# SNMP Versions
SNMP_VERSION_1 = "1"
SNMP_VERSION_2C = "2c"
SNMP_VERSION_3 = "3"

SNMP_VERSIONS = [SNMP_VERSION_1, SNMP_VERSION_2C, SNMP_VERSION_3]

# Config Keys — shared
CONF_COMMUNITY_READ = "community_read"
CONF_COMMUNITY_WRITE = "community_write"
CONF_SNMP_VERSION = "snmp_version"
CONF_SCAN_INTERVAL = "scan_interval"

# Config Keys — SNMPv3 specific
CONF_V3_USERNAME = "v3_username"
CONF_V3_AUTH_PROTOCOL = "v3_auth_protocol"
CONF_V3_AUTH_KEY = "v3_auth_key"
CONF_V3_PRIV_PROTOCOL = "v3_priv_protocol"
CONF_V3_PRIV_KEY = "v3_priv_key"
CONF_V3_CONTEXT_NAME = "v3_context_name"
CONF_V3_CONTEXT_ENGINE_ID = "v3_context_engine_id"

# SNMPv3 Auth Protocols
V3_AUTH_NONE = "none"
V3_AUTH_MD5 = "MD5"
V3_AUTH_SHA = "SHA"
V3_AUTH_SHA224 = "SHA-224"
V3_AUTH_SHA256 = "SHA-256"
V3_AUTH_SHA384 = "SHA-384"
V3_AUTH_SHA512 = "SHA-512"

V3_AUTH_PROTOCOLS = [
    V3_AUTH_NONE,
    V3_AUTH_MD5,
    V3_AUTH_SHA,
    V3_AUTH_SHA224,
    V3_AUTH_SHA256,
    V3_AUTH_SHA384,
    V3_AUTH_SHA512,
]

# SNMPv3 Privacy (Encryption) Protocols
V3_PRIV_NONE = "none"
V3_PRIV_DES = "DES"
V3_PRIV_3DES = "3DES"
V3_PRIV_AES128 = "AES-128"
V3_PRIV_AES192 = "AES-192"
V3_PRIV_AES256 = "AES-256"

V3_PRIV_PROTOCOLS = [
    V3_PRIV_NONE,
    V3_PRIV_DES,
    V3_PRIV_3DES,
    V3_PRIV_AES128,
    V3_PRIV_AES192,
    V3_PRIV_AES256,
]

# SNMPv3 Security Levels (derived from auth/priv combination)
V3_SECURITY_NOAUTH_NOPRIV = "noAuthNoPriv"
V3_SECURITY_AUTH_NOPRIV = "authNoPriv"
V3_SECURITY_AUTH_PRIV = "authPriv"

# Platforms
PLATFORMS = ["sensor", "switch", "button"]

# ======================================================
# Standard MIB OIDs
# ======================================================

# System MIB (RFC 1213)
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
OID_SYS_OBJECTID = "1.3.6.1.2.1.1.2.0"
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
OID_SYS_CONTACT = "1.3.6.1.2.1.1.4.0"
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"
OID_SYS_LOCATION = "1.3.6.1.2.1.1.6.0"

# Interfaces MIB (IF-MIB, RFC 2863)
OID_IF_NUMBER = "1.3.6.1.2.1.2.1.0"
OID_IF_TABLE = "1.3.6.1.2.1.2.2"
OID_IF_INDEX = "1.3.6.1.2.1.2.2.1.1"
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IF_TYPE = "1.3.6.1.2.1.2.2.1.3"
OID_IF_MTU = "1.3.6.1.2.1.2.2.1.4"
OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
OID_IF_PHYS_ADDRESS = "1.3.6.1.2.1.2.2.1.6"
OID_IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
OID_IF_LAST_CHANGE = "1.3.6.1.2.1.2.2.1.9"
OID_IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
OID_IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"
OID_IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
OID_IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"

# IF-MIB High-Capacity Counters (ifXTable)
OID_IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
OID_IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"
OID_IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"
OID_IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"
OID_IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"

# Interface Status Mappings
IF_ADMIN_STATUS_MAP = {1: "up", 2: "down", 3: "testing"}
IF_OPER_STATUS_MAP = {
    1: "up", 2: "down", 3: "testing",
    4: "unknown", 5: "dormant", 6: "notPresent", 7: "lowerLayerDown",
}


def format_speed(speed_mbps: int) -> str:
    """Format interface speed to human-readable string."""
    if speed_mbps == 0:
        return "unbekannt"
    elif speed_mbps >= 1000:
        return f"{speed_mbps // 1000} Gbit/s"
    return f"{speed_mbps} Mbit/s"
