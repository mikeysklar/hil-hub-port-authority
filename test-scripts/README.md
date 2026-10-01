# Port Authority test scripts

Scripts used for `../test-plan.md`; results in `../test-log.md`. They run on
the Linux host with the hub (bene.local), not on the Mac.

```sh
rsync -a test-scripts/ bene.local:port_authority/test-scripts/
ssh bene.local 'cd port_authority/test-scripts && python3 i2c_scan.py 1-2 4'
```

Needs `pyserial` and `uhubctl` (see `../bene-setup.md`), including the udev
rule that makes the per-port `disable` files writable. The scripts call uhubctl
without `-S` so it uses that sysfs method; with `-S` (raw USB requests) Linux
is not told about the power-off and keeps devices like the ESP32 V2's CH9102
listed after they lose power. Boards are always
addressed by USB path (`1-2` hub, port N), never by `ttyACM` number.

| Script | Test | What it does |
|---|---|---|
| `repl.py` | helper | CircuitPython REPL driver, syncs on `>>> ` first |
| `cycle_ports.py` | T2 | round-robin cycles over several ports, per-board check, stops each port at first failure |
| `cycle_port.py` | T2 | N uhubctl power cycles on one port, checks off/gone/back/POWER_ON (SAMD: UNKNOWN + STARTUP); RP2040/RP2350 ROM bootloader = BOOTROM |
| `reset_reason.py` | T2 | print reset and run reason of a board |
| `i2c_scan.py` | T4 | scan the hub I2C bus from the controller on a hub port |
| `ina3221_id.py` | T4 | read INA3221 ID registers (0xFE, 0xFF, 0x00) |
| `i2c_compare.py` | T4 debug | reads via board.STEMMA_I2C() vs fresh busio.I2C |
| `controller/code.py` | setup | idle sketch for the Adalogger I2C controller (CP 11.0.0-alpha.1) |
| `controller/oled_ports.py` | T12 | `code.py` for the controller: SSD1306 OLED on STEMMA2 shows ports 1-3 V/mA (INA3221) and on/off for all 4 pushed from the host |
| `oled_push.py` | T12 | host side: sends `PA 1101` (uhubctl power bits, ports 1-4) to the controller every second |
| `oled_demo.sh` | T12 | switches ports off/on one at a time for the OLED demo |
| `watch_hub.sh` | T7 | print every change in which devices are on a hub, for N seconds |
| `ina3221_volts.py` | T5/T8 | INA3221 bus voltage and current on ports 1-3, min/avg/max |
| `ina_ramp.py` | T8 debug | fast INA3221 capture of a port VBUS ramp or rail dip during uhubctl power-on |
| `backup_repl.py` | setup | back up every file on a board over the serial REPL (base64), for boards with no drive |
| `ina_inrush.py` | T5/T11 | fast INA3221 current capture of a board's power-on on ports 1-3, ~288 us/sample for ~2.3 s |
| `chain_cut.py` | T11 | cut the upstream port of a chained hub; compares a native-USB board's uptime before and after |
| `ina_channel_map.py` | T5 | map INA3221 channels to ports by switching one port off at a time |
| `cold_compare.sh` | T4 debug | uhubctl cold boot of the controller, then i2c_compare.py, N times |
| `smbus_probe.py` | T9 | scan, then block-read register 0x00 at the hub's SMBus address 0x2C (DIP `1 1 1 0`) |
| `smbus_race.py` | T9 debug | probe 0x2C every 20 ms for N seconds while SW1 resets the hub, prints ACK/NACK changes |
| `eeprom_dump.py` | T9 | read-only hex dump of the hub config EEPROM (24LC02, 0x50); needs DIP 1-3 on |
| `i2c_lines.py` | T9 debug | sample SCL/SDA levels on the controller to spot a bus held low |
| `uf2_to_bin.py` | T13 | convert a UF2 to a raw image for openocd `program`; prints family, base and size |
| `swd_port.sh` | T13 | SWD attach with the port off (expect fail) and on (reset halt, resume), RP2350 + Debug Probe |

`ina3221_id.py` retries each read up to 5 times and prints every `ETIMEDOUT`,
see the T4 open item in `../test-log.md`.

Controller location: scripts default to the Adalogger on hub port 4. Set
`PA_CTRL=<usb path>` (for example `PA_CTRL=1-1` when it is plugged straight
into bene) to point them at the controller elsewhere.
