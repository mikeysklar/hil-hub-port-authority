# Port Authority (Smart HIL Hub Rev C): findings

Running summary for the final report. Evidence and raw output for every row
are in `test-log.md` and `results/`; scripts in `test-scripts/`. Boards tested:
hub A and hub B from the 10-board JLC run, design at commit `461a9006b`.

Status: **Works** confirmed on hardware, **Problem** confirmed, **Open**
not yet tested or not conclusive.

## Hub features

| Feature | Status | Result |
|---|---|---|
| USB enumeration (USB2514B, Multi-TT, 4 ports) | Works | `0424:2514`, TT per port, per-port power and over-current reported |
| Per-port power switching (uhubctl) | Works | Every cutoff clean on both hubs (port reads `0000 off`, board drops, VBUS 0.000 V measured) |
| Hub reset slide switch SW1 | Works | Hub and all ports drop and return; ports are power-cycled too |
| I2C via STEMMA QT, INA3221 at 0x40 | Works | ID registers read `TI` / `3220` |
| Current monitoring, ports 1-3 | Works | Channel N = port N, no crosstalk, 0 mA / 0 V when off; port 4 unmonitored by design |
| External 5 V input (barrel jack) | Works | Hot-plug without disconnect; 4 A supply as stiff as USB-C |
| Bus-powered mode, DIP `0 0 0 1` | Works | Reports `0xa0` Bus Powered, MaxPower 100 mA; per-port switching unchanged. Default `0 0 0 0` reports Self Powered regardless of source, by design |
| No USB serial number | Note | Two hubs can only be told apart by USB path |
| STEMMA2 pass-through | Works | OLED on STEMMA2 scans at 0x3D alongside the INA3221 at 0x40, same bus as STEMMA1 |
| INA3221 accuracy vs meter | Rough check | Battery pack charging on port 2: INA3221 1.15-1.17 A, user's meter 1.2 A (within ~5%). One point only; no low-current check |
| Port LEDs, green | Works | Follows uhubctl port power on/off (user, daily use) |
| Over-current limit and red LED | Works well enough, red not pursued | Ports deliver at least 1.17 A continuously, beyond the ~1 A design target. Red LED never triggered and not tested further (decision 2026-10-01). Red = AP22653 FAULT (also OCS to the hub), after a ~6 ms blanking time, auto-recovering. Battery pack held 1.17 A for 30 s with green LED and no OC reported; Pi 4 + drive peaked 1.10-1.24 A briefly without a fault. |
| Port power under heavy load | Note | Pi 4 + external drive on one port: 0.65 A idle, 0.9-1.0 A busy, peaks to 1.24 A; port sagged to 3.87 V and the Pi browned out and rebooted twice with no fault flagged. Whole-hub supply sagged too (another port 5.10 V to 4.69-4.82 V) on the 4 A barrel. Guide: Pi-class loads are at this port's edge |
| SMBus mode, DIP `1 1 1 0` | Problem, parked | Hub stays off USB but never answers at 0x2C. See problems below |
| EEPROM mode, DIP `1 1 1 1` | Problem, parked | EEPROM ships blank (all `0xFF`); hub does not enumerate. Needs a programmed EEPROM |
| JST-XH per-port connectors | Open | |
| Chaining two hubs, USB | Works, with a restriction | Hub B on hub A port 4: nested uhubctl path `1-1.4` works, hub B ports switch 5/5, cutting hub A port 4 power-cycles hub B and its boards (empty 6/6, Feather RP2040 5/5, thumb drive 5/5). **Restriction:** with an ESP32 V2 on hub B, hub B never recovers from that cut (see problems). Keep USB-serial boards on the top-level hub, or switch their own port instead |
| Chaining two hubs, I2C | Open | Needs hub B's INA3221 A0 jumper bridged (0x41) |
| I2C display on STEMMA | Works | Adafruit 326 (0.96" 128x64 SSD1306, 0x3D) on STEMMA2: `controller/oled_ports.py` shows V/mA for ports 1-3 from the INA3221; `oled_push.py` sends on/off for all 4 from uhubctl. Port changes show within about a second |
| SWD / openocd through the hub | Works | Feather RP2350: attach, `reset halt`, resume; `cannot read IDR` with the port off. 30/30 clean power cycles with the probe attached (no back-feed). RP2350 needs the raspberrypi openocd fork |
| macOS | Works (user report) | Daily use on a Mac mini M4 Pro, macOS 26.6.2, Homebrew uhubctl 2.6.0, no sudo. Power control, bootloader entry and hard resets fine with Feather RP2350, Feather ESP32-S3, Feather RP2040, QT Py ESP32-S3. Hub was three deep behind two Realtek hubs |

## Problems found

| Problem | Status | Detail |
|---|---|---|
| STEMMA QT back-feeds an unpowered controller | Problem, confirmed | 0.98 V on the controller's 3.3 V rail with its port off. Caused about 1 in 10 ROM bootloader boots on the Feather RP2040 Adalogger (7/70 + 1/6 + 1/20 + 1/4 with cable; 70/70 clean without). Guide note now; I2C buffer with power-off isolation in a later rev |
| Linux keeps USB-serial boards listed after power-off | Fixed (host setup) | With `uhubctl -S` the kernel is not told. Fixed by the udev rule for the per-port `disable` files; ESP32 V2 now drops in 5 ms |
| Intermittent INA3221 read timeouts | Not the hub | Followed the controller's old dev firmware (SDIO build + SD benchmark). 0 errors in 60 reads after flashing CP 11.0.0-alpha.1 |
| Barrel jack suspected | Not the cause | Coincided with the STEMMA cable coming loose. Cheap USB-to-barrel adapter does dip the rail more (4.77 V vs 4.98 V) but stays in spec |
| Chained hub loops after its upstream port is cut, with an ESP32 V2 on it | Open, workaround | Hub B enumerates, `hub_ext_port_status failed (err = -71)` ~0.1 s later, disconnects, repeats forever. Same bus-powered or on its barrel, after a hub B reset, with autosuspend off. Not current: same ~900 mA capacitor spike as an RP2350, the V2's extra ~140 mA comes ~1 s later. Suspect (untested): its CH9102 connects at full speed the instant power arrives, mid hub start-up. Fine on the top-level hub (days of use, survives hub A resets). Workarounds: switch the V2's own port; or power hub B ports on one at a time |
| SMBus and EEPROM modes do not start | Open, parked | Both: off USB, no 0x2C, host sees a failed low-speed device at every reset. Theory (unconfirmed): `1 1 1 0` latches EEPROM mode, and the blank EEPROM sets register 0xFA bit 0, swapping upstream D+/D-. Untested discriminator: `0 1 1 0`. Probing the bus during reset left SCL held low |

## Host setup needed (for the guide)

- `uhubctl` package, udev rule for vendors `0424` and `0bda` (plugdev), and
  the rule for the per-port `disable` files (see `test-log.md`).
- openocd: stock 0.12.0 works for RP2040 only; RP2350 needs the
  raspberrypi fork (`~/.local/openocd-rp2350` on bene, copied from bravo).
- Mount board drives over SSH with `gio mount` through the desktop session.
