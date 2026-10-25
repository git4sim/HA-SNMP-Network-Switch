# Changelog

All notable changes to this integration are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- **PoE control and status** for switches that implement the POWER-ETHERNET-MIB (RFC 3621), per PoE-capable port ([#10]):
  - `switch.<port>_poe`: turns PoE on/off (`pethPsePortAdminEnable`), with the detection status as an attribute. Needs write access.
  - `sensor.<port>_poe_status`: detection status (`disabled`, `searching`, `delivering_power`, `fault`, `test`, `other_fault`), translated into English and German.
  - PoE entities are only created for ports the switch reports in its PoE table. Switches without PoE are not affected.
  - On stacked switches, writes go to the port's own PoE group (`pethPsePortGroupIndex`).
- Test suite (`python3 -m pytest tests`). It stubs Home Assistant and pysnmp, so it needs no extra dependencies.

### Changed
- **Virtual interfaces are no longer treated as ports** ([#9]). VLAN SVIs, loopbacks and tunnels (ifType 24, 53, 131, 135, 136) no longer get port switches, traffic/error sensors or alias entities. This also stops you from turning off the management interface (e.g. `vlan1` on Aruba CX) by accident.
- The **Port Count** sensor now counts the ports that were found instead of reporting `ifNumber`. It falls back to `ifNumber` if no interface data is available.

### Fixed
- **Entities went unavailable after saving options** until Home Assistant was restarted. The entry is now reloaded through Home Assistant ([#11]).
- **"Detected blocking call to open/listdir … inside the event loop" warnings** on startup. All required pysnmp MIBs are now preloaded in the executor, one module at a time. Before, the missing `IF-MIB` silently stopped the preload ([#8], [#12]).

### Upgrade notes
- Existing installs keep the old entities of virtual interfaces (e.g. `vlan1`) as *unavailable*. They can be deleted under *Settings → Devices & services → Entities*.

[Unreleased]: https://github.com/git4sim/HA-SNMP-Network-Switch/compare/main...claude/focused-newton-f8dc9h
[#8]: https://github.com/git4sim/HA-SNMP-Network-Switch/issues/8
[#9]: https://github.com/git4sim/HA-SNMP-Network-Switch/pull/9
[#10]: https://github.com/git4sim/HA-SNMP-Network-Switch/pull/10
[#11]: https://github.com/git4sim/HA-SNMP-Network-Switch/pull/11
[#12]: https://github.com/git4sim/HA-SNMP-Network-Switch/pull/12
