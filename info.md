# SNMP Network Switch

<p align="center">
  <img src="custom_components/snmp_switch/logo.png" alt="SNMP Switch Logo" width="180">
</p>

<p align="center">
  <strong>Bind managed network switches into Home Assistant via SNMP</strong><br>
  Monitor port status, traffic & errors · Toggle ports · Edit switch settings
</p>

<p align="center">
  <img src="https://img.shields.io/badge/HACS-Custom-orange.svg" />
  <img src="https://img.shields.io/badge/HA%20Version-2023.1%2B-blue" />
  <img src="https://img.shields.io/badge/SNMP-v1%20%7C%20v2c-green" />
</p>

---

## ✨ Features

- 📊 **System sensors** – Description, Uptime, Contact, Location, Name
- 🔌 **Per-port sensors** – Status, RX/TX traffic, error counters
- 🔘 **Port switches** – Enable/disable individual ports (requires write community)
- ⚙️ **SNMP SET services** – Set port alias, contact, location & system name
- 🔄 **Auto-discovery** – Port count detected automatically at setup
- 🔁 **Configurable poll interval** – 10 s to 1 h

## 📦 Supported Hardware

Works with any SNMP v1/v2c managed switch:

| Vendor | Tested |
|---|---|
| Cisco IOS / IOS-XE | ✅ |
| HPE / ProCurve / Aruba | ✅ |
| Ubiquiti UniFi | ✅ |
| TP-Link TL-SG series | ✅ |
| Netgear Insight | ✅ |
| Generic (IF-MIB compatible) | ✅ |

## 🚀 Installation via HACS

1. Open HACS → **Integrations** → ⋮ → *Custom Repositories*
2. Add `https://github.com/YOUR_USER/ha-snmp-switch` as **Integration**
3. Search for **SNMP Network Switch** and install
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration → SNMP Network Switch**
