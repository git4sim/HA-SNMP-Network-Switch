<p align="center">
  <img src="custom_components/snmp_switch/logo.png" alt="SNMP Network Switch" width="180">
</p>

<h1 align="center">SNMP Network Switch</h1>

<p align="center">
  Home Assistant Integration für verwaltete Netzwerkswitches via SNMP
</p>

<p align="center">
  <a href="https://github.com/git4sim/HA-SNMP-Network-Switch/releases">
    <img src="https://img.shields.io/github/v/release/git4sim/HA-SNMP-Network-Switch?style=for-the-badge&color=0abf53" alt="Release">
  </a>
  <a href="https://github.com/hacs/integration">
    <img src="https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge" alt="HACS">
  </a>
  <a href="https://github.com/git4sim/HA-SNMP-Network-Switch/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/git4sim/HA-SNMP-Network-Switch/validate.yaml?style=for-the-badge&label=CI" alt="CI">
  </a>
  <img src="https://img.shields.io/badge/HA%20Version-2023.1%2B-blue?style=for-the-badge" alt="HA Version">
  <img src="https://img.shields.io/badge/SNMP-v1%20%7C%20v2c-teal?style=for-the-badge" alt="SNMP">
</p>

---

## 🚀 Installation via HACS

**Empfohlener Weg – ein Klick:**

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=git4sim&repository=HA-SNMP-Network-Switch&category=integration)

**Oder manuell in HACS:**

1. HACS → **Integrationen** → ⋮ → *Benutzerdefinierte Repositories*
2. URL: `https://github.com/git4sim/HA-SNMP-Network-Switch` · Kategorie: **Integration**
3. **SNMP Network Switch** suchen → **Herunterladen**
4. Home Assistant neu starten
5. **Einstellungen → Geräte & Dienste → + Integration → SNMP Network Switch**

---

## 📌 Übersicht

Diese Integration bindet **verwaltete Netzwerkswitches** via **SNMP v1/v2c** in Home Assistant ein.

Mit nur einem Read-Community-String bekommst du vollständiges Monitoring.  
Trägst du zusätzlich einen Write-Community-String ein, kannst du Ports direkt aus HA schalten und Geräteeigenschaften setzen.

---

## ✨ Was kann die Integration?

### 📊 Sensoren
| Entity | Beschreibung |
|---|---|
| `sensor.*_beschreibung` | Gerätebeschreibung (sysDescr) |
| `sensor.*_uptime` | Betriebszeit in Sek. + lesbares Attribut |
| `sensor.*_kontakt` | sysContact |
| `sensor.*_systemname` | sysName |
| `sensor.*_standort` | sysLocation |
| `sensor.*_anzahl_ports` | Port-Anzahl + Ports Up/Down |
| `sensor.*_portX_status` | Betriebsstatus pro Port |
| `sensor.*_portX_rx` | Empfangene Bytes (HC, 64-bit) |
| `sensor.*_portX_tx` | Gesendete Bytes (HC, 64-bit) |
| `sensor.*_portX_fehler` | Fehler-Counter pro Port |

### 🔌 Switches *(nur mit Write-Community)*
| Entity | Beschreibung |
|---|---|
| `switch.*_portX` | Port ein-/ausschalten (`ifAdminStatus`) |

### 🔘 Buttons
| Entity | Beschreibung |
|---|---|
| `button.*_aktualisieren` | Sofortiger SNMP-Poll |

### ⚙️ Services *(nur mit Write-Community)*
| Service | Beschreibung |
|---|---|
| `snmp_switch.set_port_alias` | Port-Beschriftung (ifAlias) setzen |
| `snmp_switch.set_sys_contact` | sysContact setzen |
| `snmp_switch.set_sys_location` | sysLocation setzen |
| `snmp_switch.set_sys_name` | sysName setzen |

---

## 🏷️ Unterstützte Geräte

Alle Geräte mit **IF-MIB (RFC 2863)** Support funktionieren – das ist praktisch jeder verwaltete Switch:

| Hersteller | Modelle | Getestet |
|---|---|---|
| **Cisco** | IOS, IOS-XE, NX-OS | ✅ |
| **HPE / Aruba** | ProCurve, ArubaOS | ✅ |
| **Ubiquiti** | UniFi USW Serie | ✅ |
| **TP-Link** | TL-SG2xxx, TL-SG3xxx | ✅ |
| **Netgear** | GS3xx, MS-Serie | ✅ |
| **MikroTik** | RouterOS mit SNMP | ✅ |
| **Andere** | Jedes IF-MIB kompatibles Gerät | ✅ |

---

## ⚙️ Einrichtung

| Feld | Pflicht | Standard | Beschreibung |
|---|---|---|---|
| **IP-Adresse** | ✅ | – | Hostname oder IP des Switches |
| **Port** | – | `161` | SNMP UDP-Port |
| **Community (Lesen)** | – | `public` | Read-only Community String |
| **Community (Schreiben)** | – | *(leer)* | Aktiviert Switches & Services |
| **SNMP Version** | – | `2c` | v1 oder v2c |
| **Gerätename** | – | *(sysName)* | Anzeigename in HA |
| **Abfrageintervall** | – | `30` | Sekunden (10–3600) |

---

## 🔧 Switch-Konfiguration

### Cisco IOS / IOS-XE
```
snmp-server community public RO
snmp-server community private RW
```

### HPE ProCurve / Aruba
```
snmp-server community "public" operator unrestricted
snmp-server community "private" manager unrestricted
```

### Ubiquiti UniFi
**Controller → Settings → System → SNMP** → Community String eintragen

### TP-Link TL-SG Serie
**Admin UI → SNMP → Community Config → Add**

### MikroTik RouterOS
```
/snmp set enabled=yes
/snmp community add name=public read-access=yes write-access=no
/snmp community add name=private read-access=yes write-access=yes
```

---

## 🤖 Automatisierungen

### Port nachts deaktivieren
```yaml
automation:
  - alias: "Gäste-WLAN-Port nachts aus"
    trigger:
      - platform: time
        at: "23:30:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.bueroswitch_ge0_8
```

### Alarm bei Port-Fehlern
```yaml
automation:
  - alias: "Switch Port-Fehler Alarm"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bueroswitch_ge0_1_fehler
        above: 50
    action:
      - service: notify.pushover
        data:
          title: "⚠️ Switch Fehler"
          message: "Port 1 hat über 50 Fehler!"
```

---

## 🐛 Fehlersuche

### Verbindung testen
```bash
snmpwalk -v2c -c public 192.168.1.1 1.3.6.1.2.1.1.1.0
```

### Debug-Logging
```yaml
logger:
  default: warning
  logs:
    custom_components.snmp_switch: debug
```

| Problem | Lösung |
|---|---|
| *Cannot connect* | Firewall prüfen (UDP 161), SNMP aktiviert? |
| *Invalid auth* | Community String Groß-/Kleinschreibung beachten |
| *Switch entities fehlen* | Write-Community konfiguriert? |
| *Keine Port-Sensoren* | ifTable per `snmpwalk` prüfen |

---

## 🤖 Vibecoded

> *Dieses Projekt wurde vollständig mit KI-Unterstützung entwickelt – vom ersten Konzept bis zum fertigen HACS-Addon.*

**Vibecoding** beschreibt den Workflow, bei dem du deine Idee in natürlicher Sprache formulierst und KI den Code schreibt. Du bleibst Architekt und Qualitätsprüfer – die KI übernimmt die Implementierung.

So entstand dieses Addon:

```
"Baue eine HA Integration für SNMP Netzwerkswitches"
        ↓
  Vollständiger Python-Code für alle Plattformen
  HACS-Struktur, Manifest, Config Flow, Coordinator
  Logo generiert, README geschrieben
  GitHub Actions Workflows erstellt
        ↓
  Fertig. In einem Gespräch.
```

**Stack:** [Claude](https://claude.ai) (Anthropic) · Python · Home Assistant · pysnmp

Mehr zum Thema Vibecoding: [Andrej Karpathy on X](https://x.com/karpathy/status/1886192184808149383)

---

## 📐 Architektur

```
snmp_switch/
├── __init__.py          # Setup, Services
├── manifest.json        # HACS / HA Metadaten
├── config_flow.py       # UI-Setup-Assistent
├── coordinator.py       # DataUpdateCoordinator
├── snmp_client.py       # pysnmp Wrapper (GET/SET/WALK)
├── sensor.py            # Sensor-Entities
├── switch.py            # Switch-Entities (Port toggle)
├── button.py            # Button (Refresh)
├── const.py             # OIDs, Konstanten
├── services.yaml        # Service-Definitionen
├── strings.json         # UI-Texte
├── translations/
│   ├── de.json          # Deutsch
│   └── en.json          # Englisch
├── logo.png             # Integration Logo (512×512)
└── icon.png             # HACS Icon (256×256)
```

---

## 📝 Changelog

### v1.0.0
- 🎉 Initiale Veröffentlichung
- System-Sensoren (sysDescr, sysUpTime, sysContact, sysName, sysLocation)
- Interface-Sensoren pro Port (Status, RX/TX, Fehler)
- Port-Switches (ifAdminStatus SET)
- Services: set_port_alias, set_sys_contact, set_sys_location, set_sys_name
- UI-Setup via Config Flow
- SNMP v1 & v2c Support
- 64-bit Traffic Counter (ifHCInOctets / ifHCOutOctets)
- Deutsche & Englische UI-Übersetzungen

---

## 🤝 Contributing

Pull Requests sind willkommen!

1. Fork erstellen
2. Feature-Branch anlegen: `git checkout -b feature/neue-funktion`
3. PR öffnen gegen `main`

---

## 📄 Lizenz

MIT License – siehe [LICENSE](LICENSE)

---

<p align="center">
  Made with ❤️ &amp; 🤖 for the Home Assistant community<br>
  <sub>Vibecoded with <a href="https://claude.ai">Claude</a> · <a href="https://github.com/git4sim/HA-SNMP-Network-Switch">github.com/git4sim/HA-SNMP-Network-Switch</a></sub>
</p>
