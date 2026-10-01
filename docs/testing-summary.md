# Port Authority 4-port hub: testing summary

Smart HIL Hub Rev C, first 10-board JLC run. Tested 2026-09-24 to 2026-10-01
on Linux (bene, Ubuntu 26.04) and macOS (Mac mini M4 Pro). Details in
`test-log.md` and `findings.md`; scripts, cases and photos in
<https://github.com/mikeysklar/hil-hub-port-authority>.

## Concerns

### 1. STEMMA QT back-feeds an unpowered I2C controller

- With the controller's own port switched off, the hub's I2C lines held its
  3.3 V rail at 0.98 V (0 V with the cable out).
- On a Feather RP2040 Adalogger this caused about 1 in 10 power-ons to land
  in the ROM bootloader. 70/70 clean with the cable unplugged.
- Same result on two hubs with two different 5 V supplies.
- Two paths: SDA/SCL through the BSS138 level shifter (hub side pulled up to
  the hub's 3.3 V), and STEMMA V+. A diode on V+ blocks only one of them.
- **Suggested fix, later rev:** replace the BSS138 shifter with an I2C
  buffer that isolates when either side is unpowered. Candidates: PCA9517A,
  TCA9617A (not yet checked against their datasheets).
- **Now, in the guide:** keep the I2C controller always powered (a port that
  is never switched, or another hub), or unplug the STEMMA cable before
  cutting its port.

### 2. A chained hub with a Feather ESP32 V2 never comes back after its upstream port is cut

- Hub B on hub A port 4. Cutting and restoring port 4 power-cycles hub B.
  With an ESP32 V2 on hub B, hub B enumerates, fails about 0.1 s later
  (`hub_ext_port_status failed (err = -71)`), disconnects, and repeats
  forever.
- Fine: hub B empty (6/6), Feather RP2040 (5/5), USB thumb drive (5/5),
  and the V2 on the top-level hub (days of use, survives hub resets).
- Ruled out: hub B's supply (fails bus-powered and on its barrel), a stuck
  hub B, Linux autosuspend, and current (same ~900 mA capacitor spike as an
  RP2350; the V2's only extra is a ~140 mA burst about 1 s later).
- Suspect, untested: the V2's CH9102 USB-serial chip connects at full speed
  the instant it gets power, while hub B is still starting up.
- **Workaround:** keep USB-serial boards on the top-level hub, use chained
  hubs for native-USB boards, and power-cycle the board's own port rather
  than the port feeding a chained hub.

## Tested, works

- Per-port power with uhubctl on Linux and macOS (Homebrew 2.6.0), no sudo.
  Clean cutoffs on two hubs: port reads `0000 off`, VBUS 0.000 V.
- Power cycling Feather M0, RP2040, RP2350 and ESP32 V2; RP2350 30/30 with a
  Debug Probe attached.
- Current monitoring, ports 1-3: channel N = port N, no crosstalk;
  1.15-1.17 A where a USB meter read 1.2 A.
- At least 1.17 A per port continuously (battery pack, 30 s, no fault).
- Green port LEDs follow port power.
- SW1 hub reset; external 5 V hot-plug.
- DIP `0 0 0 1` reports Bus Powered.
- STEMMA2 pass-through and an SSD1306 OLED status display (live V/mA per
  port, on/off for all four).
- SWD through the hub: Feather RP2350 attach, halt, flash and verify in
  11.2 s with a Raspberry Pi Debug Probe.
- USB chaining: nested `uhubctl -l 1-1.4` paths and per-port switching on
  the second hub, with the restriction in concern 2.
- EEPROM mode (DIP `1 1 1 1`) once programmed: `eeprom_write.py` wrote
  custom strings, and the hub enumerates as Adafruit Industries / Port
  Authority / serial `PA-A`. The serial lets scripts tell hubs apart.

## Tested, doesn't work

- SMBus DIP mode (`1 1 1 0`): hub stays off USB, never answers at 0x2C,
  host sees a failed low-speed device at every reset. Parked.
- EEPROM mode with the EEPROM as shipped (blank, all `0xFF`): same failure.
  Fixed by programming it (see above).
- Raspberry Pi 4 with an external drive on one port: 0.65 A idle, peaks to
  1.24 A; the port sagged to 3.87 V and the Pi browned out and rebooted
  twice with no fault shown. Power Pi-class loads separately.

## Untested

- I2C chaining of two hubs (needs the second hub's INA3221 A0 jumper bridged
  for 0x41).
- Red fault LED: never triggered, no load exceeded the port limit. Not
  pursued, since the ports already carry more than 1 A.
- JST-XH per-port connectors.
