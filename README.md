<p align="center">
  <img src="custom_components/snmp_switch/logo.png" alt="SNMP Network Switch" width="200">
</p>

<h1 align="center">SNMP Network Switch</h1>

<p align="center">
  Home Assistant Integration für verwaltete Netzwerkswitches via SNMP
</p>

<p align="center">
  <a href="https://github.com/YOUR_USER/ha-snmp-switch/releases"><img src="https://img.shields.io/github/v/release/YOUR_USER/ha-snmp-switch?style=for-the-badge&color=0abf53" alt="Release"></a>
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge" alt="HACS"></a>
  <a href="https://github.com/YOUR_USER/ha-snmp-switch/actions"><img src="https://img.shields.io/github/actions/workflow/status/YOUR_USER/ha-snmp-switch/validate.yaml?style=for-the-badge&label=CI" alt="CI"></a>
  <img src="https://img.shields.io/badge/HA%20Version-2023.1%2B-blue?style=for-the-badge" alt="HA Version">
</p>

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

## 📦 Installation

### Via HACS *(empfohlen)*

1. Stelle sicher dass [HACS](https://hacs.xyz) installiert ist
2. Öffne HACS → **Integrationen** → Drei-Punkte-Menü → **Benutzerdefinierte Repositories**
3. Füge `https://github.com/YOUR_USER/ha-snmp-switch` als Kategorie **Integration** hinzu
4. Suche nach **SNMP Network Switch** und klicke **Herunterladen**
5. Home Assistant neu starten

### Manuell

1. Lade die neueste `snmp_switch.zip` von den [Releases](https://github.com/YOUR_USER/ha-snmp-switch/releases) herunter
2. Entpacke nach `config/custom_components/snmp_switch/`
3. Starte Home Assistant neu

---

## ⚙️ Einrichtung

1. **Einstellungen → Geräte & Dienste → + Integration hinzufügen**
2. Nach **"SNMP Network Switch"** suchen
3. Konfigurationsformular ausfüllen:

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

Damit HA sich verbinden kann, muss SNMP auf dem Switch aktiviert sein:

### Cisco IOS / IOS-XE
```
snmp-server community public RO
snmp-server community private RW
snmp-server location "Serverraum EG"
snmp-server contact "IT Admin <admin@company.com>"
```

### HPE ProCurve / Aruba
```
snmp-server community "public" operator unrestricted
snmp-server community "private" manager unrestricted
```

### Ubiquiti UniFi
**Controller → Settings → System → SNMP**  
Community String eintragen, SNMP aktivieren.

### TP-Link TL-SG Serie
**Admin UI → SNMP → Community Config → Add**  
`public` (Read-Only) und `private` (Read-Write)

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

### Port-Beschriftung via Service setzen
```yaml
service: snmp_switch.set_port_alias
data:
  entry_id: "abc123"    # Aus Einstellungen → Geräte & Dienste → Integration → Entry ID
  if_index: 5           # Port-Index
  alias: "NAS-Server"
```

---

## 🐛 Fehlersuche

### Verbindung testen (Linux / macOS)
```bash
snmpwalk -v2c -c public 192.168.1.1 1.3.6.1.2.1.1.1.0
```

### Debug-Logging aktivieren
```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.snmp_switch: debug
```

### Häufige Probleme

| Problem | Lösung |
|---|---|
| *Cannot connect* | Firewall prüfen (UDP 161), SNMP auf Switch aktiviert? |
| *Invalid auth* | Community String Groß-/Kleinschreibung beachten |
| *Switch entities fehlen* | Write-Community konfiguriert? |
| *Keine Port-Sensoren* | ifTable per `snmpwalk` testen |

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
├── strings.json         # UI-Texte (DE)
├── logo.png             # Integration Logo (512x512)
└── icon.png             # HACS Icon (256x256)
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

---

## 🤝 Contributing

Pull Requests sind willkommen! Bitte:
1. Fork erstellen
2. Feature-Branch anlegen (`git checkout -b feature/neue-funktion`)
3. Tests hinzufügen
4. PR öffnen

---

## 📄 Lizenz

MIT License – siehe [LICENSE](LICENSE)

---

<p align="center">Made with ❤️ for the Home Assistant community</p>
