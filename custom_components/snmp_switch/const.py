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

# Config Keys
CONF_COMMUNITY_READ = "community_read"
CONF_COMMUNITY_WRITE = "community_write"
CONF_SNMP_VERSION = "snmp_version"
CONF_SCAN_INTERVAL = "scan_interval"

# Platforms
PLATFORMS = ["sensor", "switch", "button"]

# ======================================================
# Standard MIB OIDs
# ======================================================

# System MIB (RFC 1213)
OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"         # sysDescr – Gerätebeschreibung
OID_SYS_OBJECTID = "1.3.6.1.2.1.1.2.0"      # sysObjectID
OID_SYS_UPTIME = "1.3.6.1.2.1.1.3.0"        # sysUpTime (in 1/100 sec)
OID_SYS_CONTACT = "1.3.6.1.2.1.1.4.0"       # sysContact (R/W)
OID_SYS_NAME = "1.3.6.1.2.1.1.5.0"          # sysName (R/W)
OID_SYS_LOCATION = "1.3.6.1.2.1.1.6.0"      # sysLocation (R/W)

# Interfaces MIB (IF-MIB, RFC 2863)
OID_IF_NUMBER = "1.3.6.1.2.1.2.1.0"          # ifNumber – Anzahl Interfaces
OID_IF_TABLE = "1.3.6.1.2.1.2.2"             # ifTable
OID_IF_INDEX = "1.3.6.1.2.1.2.2.1.1"         # ifIndex
OID_IF_DESCR = "1.3.6.1.2.1.2.2.1.2"         # ifDescr – Port-Bezeichnung
OID_IF_TYPE = "1.3.6.1.2.1.2.2.1.3"          # ifType
OID_IF_MTU = "1.3.6.1.2.1.2.2.1.4"           # ifMtu
OID_IF_SPEED = "1.3.6.1.2.1.2.2.1.5"         # ifSpeed (bps)
OID_IF_PHYS_ADDRESS = "1.3.6.1.2.1.2.2.1.6"  # ifPhysAddress (MAC)
OID_IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"  # ifAdminStatus (R/W): 1=up, 2=down
OID_IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"   # ifOperStatus: 1=up, 2=down, 3=testing
OID_IF_LAST_CHANGE = "1.3.6.1.2.1.2.2.1.9"   # ifLastChange
OID_IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"    # ifInOctets
OID_IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"    # ifInErrors
OID_IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"   # ifOutOctets
OID_IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"   # ifOutErrors

# IF-MIB High-Capacity Counters (ifXTable)
OID_IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"           # ifName
OID_IF_HIGH_SPEED = "1.3.6.1.2.1.31.1.1.1.15"     # ifHighSpeed (Mbps)
OID_IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"          # ifAlias (R/W) – Port-Beschriftung
OID_IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"    # ifHCInOctets (64-bit)
OID_IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"  # ifHCOutOctets (64-bit)

# ======================================================
# Sensor Definitions
# ======================================================

SYSTEM_SENSORS = {
    "sys_description": {
        "name": "Beschreibung",
        "oid": OID_SYS_DESCR,
        "icon": "mdi:information-outline",
        "unit": None,
        "device_class": None,
    },
    "sys_uptime": {
        "name": "Uptime",
        "oid": OID_SYS_UPTIME,
        "icon": "mdi:clock-outline",
        "unit": None,
        "device_class": "duration",
    },
    "sys_contact": {
        "name": "Kontakt",
        "oid": OID_SYS_CONTACT,
        "icon": "mdi:account",
        "unit": None,
        "device_class": None,
        "writable": True,
    },
    "sys_name": {
        "name": "Systemname",
        "oid": OID_SYS_NAME,
        "icon": "mdi:tag-outline",
        "unit": None,
        "device_class": None,
        "writable": True,
    },
    "sys_location": {
        "name": "Standort",
        "oid": OID_SYS_LOCATION,
        "icon": "mdi:map-marker",
        "unit": None,
        "device_class": None,
        "writable": True,
    },
    "if_number": {
        "name": "Anzahl Ports",
        "oid": OID_IF_NUMBER,
        "icon": "mdi:ethernet",
        "unit": "Ports",
        "device_class": None,
    },
}

# Interface Status Mappings
IF_ADMIN_STATUS_MAP = {1: "up", 2: "down", 3: "testing"}
IF_OPER_STATUS_MAP = {1: "up", 2: "down", 3: "testing", 4: "unknown", 5: "dormant", 6: "notPresent", 7: "lowerLayerDown"}

# Interface Speed in Mbps → human readable
def format_speed(speed_mbps: int) -> str:
    """Format interface speed."""
    if speed_mbps == 0:
        return "unbekannt"
    elif speed_mbps >= 1000:
        return f"{speed_mbps // 1000} Gbit/s"
    else:
        return f"{speed_mbps} Mbit/s"
