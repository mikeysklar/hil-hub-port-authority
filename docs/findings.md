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
| STEMMA2 pass-through | Open | Needs an OLED |
| INA3221 accuracy vs meter | Open | |
| Port LEDs, over-current, red LED | Open | Over-current test gated, needs a defined load |
| SMBus mode, DIP `1 1 1 0` | Problem, parked | Hub stays off USB but never answers at 0x2C. See problems below |
| EEPROM mode, DIP `1 1 1 1` | Problem, parked | EEPROM ships blank (all `0xFF`); hub does not enumerate. Needs a programmed EEPROM |
| JST-XH per-port connectors | Open | |
| Chaining two hubs (USB and I2C) | Open | |
| I2C display on STEMMA | Open | |
| SWD / openocd through the hub | Works | Feather RP2350: attach, `reset halt`, resume; `cannot read IDR` with the port off. 30/30 clean power cycles with the probe attached (no back-feed). RP2350 needs the raspberrypi openocd fork |
| macOS | Open | |

## Problems found

| Problem | Status | Detail |
|---|---|---|
| STEMMA QT back-feeds an unpowered controller | Problem, confirmed | 0.98 V on the controller's 3.3 V rail with its port off. Caused about 1 in 10 ROM bootloader boots on the Feather RP2040 Adalogger (7/70 + 1/6 + 1/20 + 1/4 with cable; 70/70 clean without). Guide note now; I2C buffer with power-off isolation in a later rev |
| Linux keeps USB-serial boards listed after power-off | Fixed (host setup) | With `uhubctl -S` the kernel is not told. Fixed by the udev rule for the per-port `disable` files; ESP32 V2 now drops in 5 ms |
| Intermittent INA3221 read timeouts | Not the hub | Followed the controller's old dev firmware (SDIO build + SD benchmark). 0 errors in 60 reads after flashing CP 11.0.0-alpha.1 |
| Barrel jack suspected | Not the cause | Coincided with the STEMMA cable coming loose. Cheap USB-to-barrel adapter does dip the rail more (4.77 V vs 4.98 V) but stays in spec |
| SMBus and EEPROM modes do not start | Open, parked | Both: off USB, no 0x2C, host sees a failed low-speed device at every reset. Theory (unconfirmed): `1 1 1 0` latches EEPROM mode, and the blank EEPROM sets register 0xFA bit 0, swapping upstream D+/D-. Untested discriminator: `0 1 1 0`. Probing the bus during reset left SCL held low |

## Host setup needed (for the guide)

- `uhubctl` package, udev rule for vendors `0424` and `0bda` (plugdev), and
  the rule for the per-port `disable` files (see `test-log.md`).
- openocd: stock 0.12.0 works for RP2040 only; RP2350 needs the
  raspberrypi fork (`~/.local/openocd-rp2350` on bene, copied from bravo).
- Mount board drives over SSH with `gio mount` through the desktop session.
