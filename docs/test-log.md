# Port Authority (Smart HIL Hub Rev C): test log

Plan: `test-plan.md`. Host bene.local, hub USB path `1-2`.

## Setup, 2026-09-25

- S1: DIP SW2 all off (CFG_SEL 00, EEPROM unpowered, hub I2C isolated).
- S2: Adalogger moved to port 4, STEMMA QT cable to hub STEMMA1 (the one nearer the USB-A row).
- S3: Adalogger now `1-2.4`, tty `/dev/serial/by-path/pci-0000:00:14.0-usb-0:2.4:1.0`.
  Hub devnum 109 (was 34 on 09-24; it has re-enumerated since).

```
$ uhubctl -l 1-2
Current status for hub 1-2 [0424:2514, USB 2.00, 4 ports, ppps]
  Port 1: 0100 power
  Port 2: 0100 power
  Port 3: 0100 power
  Port 4: 0103 power enable connect [239a:815e Adafruit Feather RP2040 Adalogger DF6380824F7A1430]
```

## T1. Enumeration and descriptors, 2026-09-25: PASS (with findings)

`lsusb -v -d 0424:2514`, DIP all off, powered from upstream USB only (confirmed).

| Field | Value | Meaning |
|---|---|---|
| idVendor:idProduct | `0424:2514`, bcdDevice `b.b3` | USB2514B internal defaults |
| iManufacturer / iProduct / iSerial | 0 / 0 / 0 | **No strings, no serial number** |
| bDeviceProtocol | 2, alt setting 1 = TT per port | Multi-TT |
| bmAttributes | `0xe0` Self Powered, Remote Wakeup | from CFG_SEL 00 |
| MaxPower | 2 mA | |
| wHubCharacteristic | `0x0009` | per-port power switching, per-port over-current |
| bPwrOn2PwrGood | 50 x 2 ms = 100 ms | |
| DeviceRemovable | `0x00` | all ports removable (NON_REM straps 00 via R27, R7) |
| PortPwrCtrlMask | `0xff` | |

Findings:

1. **Reports Self Powered in default mode regardless of the actual source.**
   Matches Table 5-1 (CFG_SEL 00 = self-powered) and the Rev C schematic,
   where `LOCAL_PWR` is only a 100K pull-down and not tied to the TPS2117 `ST`
   output. When run from USB alone, the host believes 500 mA is available per
   port. DIP 4 on (CFG_SEL 10) should give bus-powered reporting; T9.
2. **No serial number.** Two hubs cannot be told apart by descriptor; address
   them by USB path (`uhubctl -l 1-2`), which matters for chaining (T11).
3. Descriptor and port status agree with uhubctl: `ppps`, port 4 connected.

<details><summary>Full lsusb -v</summary>

```
Bus 001 Device 109: ID 0424:2514 Microchip Technology, Inc. (formerly SMSC) USB 2.0 Hub
Negotiated speed: High Speed (480Mbps)
Device Descriptor:
  bcdUSB               2.00
  bDeviceClass            9 Hub
  bDeviceProtocol         2 TT per port
  idVendor           0x0424 Microchip Technology, Inc. (formerly SMSC)
  idProduct          0x2514 USB 2.0 Hub
  bcdDevice            b.b3
  iManufacturer           0
  iProduct                0
  iSerial                 0
  Configuration Descriptor:
    bmAttributes         0xe0
      Self Powered
      Remote Wakeup
    MaxPower                2mA
Hub Descriptor:
  nNbrPorts             4
  wHubCharacteristic 0x0009
    Per-port power switching
    Per-port overcurrent protection
    TT think time 8 FS bits
  bPwrOn2PwrGood       50 * 2 milli seconds
  bHubContrCurrent      1 milli Ampere
  DeviceRemovable    0x00
  PortPwrCtrlMask    0xff
 Hub Port Status:
   Port 1: 0000.0100 power
   Port 2: 0000.0100 power
   Port 3: 0000.0100 power
   Port 4: 0000.0103 power enable connect
Device Status:     0x0001
  Self Powered
```
</details>

## T4 (part 1). I2C scan, DIP all off, 2026-09-25: PASS

Adalogger on port 4, `board.STEMMA_I2C()` into hub STEMMA1.

```
>>> print([hex(a) for a in i2c.scan()])
['0x40']
```

Identity of 0x40 confirmed from ID registers:

```
0xfe 5449    manufacturer ID "TI"
0xff 3220    die ID, INA3221
0x0 7127     configuration register, power-on default
```

- Only 0x40, as expected with DIP 2/3 off: EEPROM (0x50) and hub SMBus (0x2C)
  are isolated. INA3221 address jumpers A0-A2 open, R15 pulls A0 to GND.
- STEMMA2 pass-through (OLED at 0x3C) still to do.

### T4 open item: intermittent ETIMEDOUT on INA3221 reads

`scan()` always finds 0x40, but register reads (`writeto_then_readfrom`)
sometimes fail with `OSError: [Errno 116] ETIMEDOUT`, in runs:

| run | result |
|---|---|
| ad hoc, 1st session | 3/3 reads ok |
| `ina3221_id.py` after `i2c_scan.py` (x2) | all reads fail, lock left held (script bug, fixed with try/finally) |
| step-by-step session | 1st read fails, 2nd ok |
| 3 sessions in one REPL, deinit between | session 1: 4 fails then ok after a scan; sessions 2-3: all ok |
| `ina3221_id.py` with retry, x3 | run 1 all ok; runs 2-3 all 5 retries fail |

Not deterministic. **Confounded:** the 5 V barrel jack was plugged in during
these runs, exact time unknown. Unknown whether it is the hub (BSS138 level
shifter, 10K pull-ups on both sides), the Adalogger/CircuitPython side, or
the cable. Needs a measured run count on each power source and a control
(same controller, a known-good I2C breakout without the hub).

## T8 (part 1). External 5 V hot-plug, 2026-09-25

5 V barrel jack plugged into X11 while running from USB, Adalogger on port 4.

- No disconnect in the kernel log; hub stayed devnum 109, Adalogger 110.
- `bmAttributes 0xe0` Self Powered, unchanged (as predicted from T1: the hub
  cannot see the power source).
- Port status unchanged: port 4 `0103`.

### T4 open item, continued: narrowed to the first `board.STEMMA_I2C()` object

Barrel jack in, DIP all off. `ina3221_id.py` 20 runs: **20/20 fail**, every
read `ETIMEDOUT`.

Frequency is not the cause: after `board.STEMMA_I2C().deinit()`, a fresh
`busio.I2C(board.SCL, board.SDA, frequency=f)` read 10/10 at each of 400k,
100k, 50k and 10k.

`i2c_compare.py 1-2 4 5`, one REPL session after the usual Ctrl-C/soft reload:

```
CASE A STEMMA_I2C as found ok 0 err 5 0000 [Errno 116] ETIMEDOUT
CASE B STEMMA_I2C again ok 0 err 5 0000 [Errno 116] ETIMEDOUT
CASE C deinit, STEMMA_I2C new ok 5 err 0 5449 None
CASE D busio.I2C 100k ok 5 err 0 5449 None
CASE E busio.I2C 400k ok 5 err 0 5449 None
CASE F STEMMA_I2C after busio ok 5 err 0 5449 None
```

- The first I2C object in the VM fails every hardware transaction; after one
  `deinit()` every later object works, including `board.STEMMA_I2C()` itself.
- `scan()` works even on the bad object because on RP2040 the zero-byte probe
  writes go through bitbangio, not the I2C peripheral
  (`ports/raspberrypi/common-hal/busio/I2C.c`, per subagent, to verify).
  That is why the scan always found 0x40.
- Each failed read costs the 1 s bus timeout (`BUS_TIMEOUT_US`).
- Root cause unknown. Not yet separated: hub vs controller (needs a control
  without the hub), soft reload vs cold boot, barrel jack in vs out.

Research leads (3 subagents: Learn guides, forums, GitHub):

- `adafruit_ina3221` reads with separate `write()` + `readinto()`, not
  `write_then_readinto()`; STEMMA_I2C is fixed at 100 kHz
  (`shared-module/board/__init__.c`). Both per subagent, to verify.
- circuitpython#2635 (open): no I2C bus recovery exists; a bad bus state
  persists until power down.
- Learn "Working with I2C devices": lower clock for clock stretching. Already
  ruled out here.
- Forum t=213402: INA228 I2C failures from high dI/dt switching noise. Lead
  only.

### T4 open item, continued: cold boot clears it, then it comes back

`cold_compare.sh 1-2 4 10 3` (uhubctl power cycle of port 4, 10 s wait,
`reset_reason.py`, then `i2c_compare.py`): **10/10 cycles all cases pass**,
`POWER_ON` every cycle, including case A (first `STEMMA_I2C`).

A few minutes later, no power cycle: `ina3221_id.py` fails every read again
and `i2c_compare.py` shows the same A/B fail, C-F pass pattern.

Controller state that differs between the two: the Adalogger is not running
stock firmware. It runs `10.3.0-alpha.3-10-g292758acc8-dirty` with the
experimental SDIO build (circuitpython PR #11090, `CIRCUITPY_SDIOIO=1`), and
`code.py` is Jeff Epler's SD benchmark: `mount_sd.py` mounts the card over
4-bit SDIO (PIO, GPIO18-23), sleeps 8 s, then writes and reads the card.
In the cold-boot runs the scripts interrupted `code.py` during that 8 s sleep,
so the benchmark I/O never ran. Between the later sessions it ran to
completion. Suspect, not proven: SDIO/PIO/DMA activity leaves the RP2040 I2C0
peripheral in a state that survives soft reloads until a deinit or power
cycle. That would make this a controller firmware issue, not the hub.

### T4 open item, resolved for hub testing: controller firmware swapped

Changes to the Adalogger, 2026-09-25:

1. Backup of CIRCUITPY (19 files, md5 verified) in `adalogger-backup-20260925/`.
2. Flashed CircuitPython **11.0.0-alpha.1** (UF2 sha256
   `6dd88ceb10d6868bcd7709623bc8bfff6ebdfafa2519ac3c6d844ed0a42a7349`),
   1200-baud touch then copy to RPI-RP2. `boot_out.txt` confirms
   `11.0.0-alpha.1 on 2026-09-24`, board ID and UID `DF6380824F7A1430`.
3. `code.py` replaced with the idle sketch `test-scripts/controller/code.py`
   (no SD, no I2C, no pins). No `boot.py` existed. `mount_sd.py`,
   `settings.toml` and the backup files left on the drive, unused.

Result, same hub, same cable, barrel jack still in:

- `i2c_compare.py`: all cases A-F pass, before and after.
- `ina3221_id.py` x20 across 20 soft reloads: **60/60 reads ok, 0 ETIMEDOUT**.
  The old firmware failed 20/20 under the same test.

Conclusion: the hub is not the cause. The failure followed the controller's
firmware/`code.py` (10.3.0-alpha.3 dirty with experimental SDIO running the SD
benchmark). Two variables changed at once (firmware and `code.py`), so this
does not isolate SDIO vs the old build. That split only matters for the SDIO
PR, not for the hub.

## T7. Hub reset (SW1), 2026-09-25: PASS

SW1 is the slide switch next to USB-A port 4 (not DIP 1; a first attempt moved
DIP 1 by mistake, nothing happened, reset back off). SW1 moved to hold for
about 5 s, then back to run. `test-scripts/watch_hub.sh 1-2 90`:

```
16:37:22.353 present: 1-2 1-2.4
16:37:31.745 present: <none>
16:37:37.888 present: 1-2
16:37:39.633 present: 1-2 1-2.4
```

Kernel log:

```
16:37:31 usb 1-2: USB disconnect, device number 109
16:37:31 usb 1-2.4: USB disconnect, device number 123
16:37:37 usb 1-2: new high-speed USB device number 9 using xhci_hcd
16:37:39 usb 1-2.4: new full-speed USB device number 10 using xhci_hcd
```

- Hub and all downstream devices drop while SW1 holds reset, and return on
  release: hub 0 s after release, Adalogger 1.7 s later. New devnums (9, 10).
- **Downstream port power is cut during hub reset.** The Adalogger reports
  `POWER_ON` / `STARTUP` afterwards, so SW1 power-cycles every port at once.
  Consistent with PRTPWR going inactive while `RESET_N` is low.
- Port status after: 1-3 `0100 power`, 4 `0103 power enable connect`.

JP1 (reset test pad) not tested; same net as SW1.

## T2. Per-port power switching, 2026-09-25 (in progress)

### Port 4, Adalogger (CP 11.0.0-alpha.1, idle code.py): 9/10

`cycle_port.py 1-2 4 10` (off `-r 30 -w 500`, 2 s off, on, 10 s settle):

```
n  off   gone  bus_s tty_s devnum reset      run
1  0000  True  1.8   1.9   11     POWER_ON   STARTUP  PASS
2  0000  True  1.8   1.9   12     POWER_ON   STARTUP  PASS
3  0000  True  1.8   2.0   13     POWER_ON   STARTUP  PASS
4  0000  True  0.6   -     14     NO-TTY     -  FAIL
5  0000  True  1.8   1.9   15     POWER_ON   STARTUP  PASS
...
10 0000  True  1.8   1.9   20     POWER_ON   STARTUP  PASS
9/10 pass
```

Control: `microcontroller.reset()` then read back gives
`ResetReason.SOFTWARE`, so the POWER_ON check can fail.

**Cycle 4 booted into the RP2040 ROM bootloader**, not CircuitPython:

```
16:40:45 usb 1-2.4: new full-speed USB device number 14 using xhci_hcd
16:40:45 usb 1-2.4: New USB device found, idVendor=2e8a, idProduct=0003, bcdDevice= 1.00
16:40:45 usb-storage 1-2.4:1.0: USB Mass Storage device detected
```

It stayed in RPI-RP2 until the next power-off; cycle 5 booted normally. It
came up at 0.6 s instead of the usual 1.8 s (the ROM enumerates faster than
CircuitPython). Port switching itself worked every cycle (`0000 off`, device
gone). One in ten is not a rate. Unknown: whether off time, VBUS decay (100 uF
on each port) or the RP2040's boot behavior on a fast power cycle is the
cause. The same board passed 10/10 on port 1 on 09-24 on the old firmware.

Script fix: `cycle_port.py` printed `NO-TTY` and hid the bootloader boot. It
now records VID:PID and reports `BOOTROM`.

### Port 4, 30 cycles at 2 s off and 30 at 5 s off: 27/30 each

Raw output: `results/t2-port4-30x-off2s.txt`, `results/t2-port4-30x-off5s.txt`.

| off time | pass | fails | failed cycles |
|---|---|---|---|
| 2 s | 27/30 | 3 BOOTROM | 11, 13, 16 |
| 5 s | 27/30 | 3 BOOTROM | 1, 8, 20 |
| (earlier) 2 s | 9/10 | 1 BOOTROM | 4 |

- Every cycle switched correctly: `0000 off`, device gone, back on the bus.
  **Port power switching is 70/70.** Every failure is the Adalogger booting
  into the RP2040 ROM bootloader (`2e8a:0003`, up at 0.6 s) instead of
  CircuitPython.
- **Off time does not matter:** 10% at both 2 s and 5 s (7/70 overall). So it
  is not the port's 100 uF failing to discharge.
- All BOOTROM boots recovered on the next power cycle.
- Remaining suspects: the power-on ramp this port delivers (AP22653 soft start
  into 100 uF plus the board's own capacitance) vs RP2040 flash boot, or the
  board itself. Needs a control: the same kind of cycle on a different
  switchable hub (bene's Realtek `1-6.3.4` has `ppps` and two RP2040 boards).
- Unexplained, minor: device numbers 24-26 and 28 were skipped during the 2 s
  run with no kernel log lines for them.

### Controls on bene's Realtek hubs (0bda:5411, ppps), 30 cycles at 2 s off

| board | hub / port | result | file |
|---|---|---|---|
| Feather RP2040 DVI | `1-6.3.4` port 4 | 30/30, 0 BOOTROM | `results/t2-control-realtek-dvi-30x-off2s.txt` |
| **Adalogger (same board)** | `1-6.3` port 2 | **30/30, 0 BOOTROM** | `results/t2-control-realtek-adalogger-30x-off2s.txt` |
| Adalogger | Port Authority `1-2` port 4 | 63/70, 7 BOOTROM | above |

- Same Adalogger, same firmware, same script: 0/30 bootloader boots on the
  Realtek hub vs 7/70 (10%) on Port Authority port 4. If the rate were 10%
  on both, 0/30 would happen about 4% of the time (0.9^30), so this points at
  the hub side, not proven.
- Still confounded: Port Authority was on the external 5 V barrel jack, the
  Realtek hubs on their own supply; only port 4 of Port Authority tested.
- Leading hypothesis, unmeasured: the VBUS rise on Port Authority's port
  (AP22653 switch into 100 uF plus the board) is slow or non-monotonic enough
  that the RP2040 flash boot fails and the ROM falls back to USB boot. The real
  measurement is a scope on port VBUS during power-on, Port Authority vs
  Realtek.

### Port 4, hub on USB-C power only (barrel jack removed): 30/30

`results/t2-port4-usbonly-30x-off2s.txt`: 30/30 pass, 0 BOOTROM.

| hub power | Adalogger on | BOOTROM |
|---|---|---|
| USB-C + 5 V barrel jack | Port Authority port 4 | 7/70 |
| USB-C only | Port Authority port 4 | 0/30 |
| Realtek hub supply | Realtek `1-6.3` port 2 | 0/30 |

The bootloader boots follow the **external 5 V input**, not the port or the
hub's switching. With the barrel jack in, ports are fed through the
TPS259470A eFuse and the TPS2117 mux's external input; on USB-C only they are
fed from upstream VBUS through the mux's other input. Not yet separated: the
hub's external power path vs the particular 5 V supply used (make/rating
unrecorded). 0/30 vs a 10% rate is about 4% likely by chance, so a repeat
with the barrel jack back in is the confirming run.

### Supply check and power-on capture with the barrel jack in (USB 2 A adapter to barrel)

Static, `ina3221_volts.py 1-2 4 20`, ports 1-3 empty: **5.016 V** on all
three channels, every sample. The adapter is not sagging at rest (eFuse UVLO
about 4.48 V per the Rev A review, same R values in Rev C).

Fast capture, `ina_ramp.py` (INA3221 one channel, bus only, 140 us
conversion, about 254 us/sample, 3000 samples; config restored to 0x7127
after). Shunts are after each AP22653 switch, so channel N reads port N VBUS.
Raw CSVs: `results/ramp-jack-in-ch*-p1-*.csv`.

Port 1's own ramp, port 1 switched on, empty port (5 trials):

| trial | 0.5 V to 4.5 V | min after reaching 4.5 V | max | end |
|---|---|---|---|---|
| 1 | 489 us | 4.776 | 5.088 | 5.016 |
| 2 | 488 us | 4.544 | 5.088 | 5.016 |
| 3 | 733 us | 4.800 | 5.096 | 5.016 |
| 4 | 732 us | 4.680 | 5.088 | 5.016 |
| 5 | 732 us | 4.776 | 5.096 | 5.024 |

Trial 2 samples: 0.19, 1.85, 3.86, 4.54, 4.86, 4.96, 5.00 V at 254 us steps,
so about 1.5 ms from off to 5.0 V. Rise time resolution is one sample
(254 us); the 488 vs 732 us split is sample quantization.

Shared rail seen on port 2 while port 1 switches on (5 trials): steady 5.016 V,
**dips to 4.768-4.784 V** for about 1 ms at switch-on, overshoots to about
5.09 V, settles at 5.02 V. Trial 1: 5.016, 4.904, 4.784, 4.864, 4.952, 4.992,
5.032 V. The dip stays above the eFuse UVLO in all 5.

Script fix: the first summary line labelled `min(v)` as "start"; it now prints
first, min, max and end separately.

Caveat: an empty port. The Adalogger adds its own input capacitance, so a
loaded port's inrush and dip will be larger. Port 4 (where the BOOTROM boots
happened) cannot be captured this way, it has no INA3221 channel and it
powers the controller.

### Same captures on USB-C power only (barrel jack unplugged)

Raw CSVs: `results/ramp-usb-only-ch*-p1-*.csv`.

| measurement (port 1 switched on, empty) | barrel jack in | USB-C only |
|---|---|---|
| static rail, ports 1-3 | 5.016 V | 5.120 V |
| rail dip on port 2 (5 trials) | to 4.768-4.784 V (-0.23 to -0.25 V) | to 4.976-4.984 V (-0.14 V) |
| rail overshoot after dip | to 5.088-5.096 V (+0.07 V over steady) | none (max 5.128-5.136, steady 5.12) |
| port 1 min after first reaching 4.5 V | 4.544-4.800 V | 4.728-4.936 V |
| port 1 off to 4.5 V | 1 to 3 samples of 254 us | same |

- The external input is about 0.1 V lower at rest, dips about 1.7x deeper at
  switch-on, and overshoots afterwards. USB-C only dips less and does not
  overshoot. That matches the external path having more source impedance
  (adapter, barrel cable, eFuse) and a regulation loop that rings.
- Even the worst dip (4.77 V) is far above what the Adalogger's 3.3 V LDO
  needs, so a simple 5 V brownout does not explain the ROM bootloader boots
  on its own. Not measured: the port VBUS and the board's 3.3 V rail during
  the first ~1.5 ms with a board attached, at better than 254 us resolution.
  That needs a scope.
- Practical conclusion for now: with this USB-to-barrel 2 A adapter, 7/70
  bootloader boots; on USB-C only 0/30. Next cheap check: a proper 5 V barrel
  supply.

### 4 A barrel supply, 2026-09-27: run aborted at cycle 6

Static rail 5.120 V (same as USB-C only). Rail dip at port 1 switch-on
4.976-4.992 V, no overshoot (`results/ramp-jack4a-ch2-p1-*.csv`), identical
to USB-C only. Not yet confirmed which input the TPS2117 had selected: the
design has no readout of `ST`.

`cycle_port.py 1-2 4 70 2`: cycles 1-5 pass; **cycle 6 booted to the ROM
bootloader** (`2e8a:0003`, devnum 67, 05:41:57). Then the whole hub dropped
twice, which the script did not survive:

```
05:42:20 usb 1-2: USB disconnect, device number 9
05:42:52 usb 1-2: new high-speed USB device number 68
05:43:07 usb 1-2: USB disconnect, device number 68
05:43:07 usb 1-2: clear tt 4 (9332) error -71
05:43:15 usb 1-2: new high-speed USB device number 70
```

Cause of the two hub drops not known yet (asked whether the supply or cables
were handled at those times). So far on the 4 A supply: 1 BOOTROM in 6.

Script fix: `cycle_port.py` crashed on `SerialException` when the board
vanished mid-read. It now records `SERIAL-ERR`, continues, and notes when the
hub itself was missing during a cycle.

### Hub B (second Rev C board), 4 A barrel supply, 2026-09-27

Swapped in hub B: same bene port (`1-2`), Adalogger on port 4, STEMMA1 cable,
DIP all off, 4 A barrel supply. Hub A is the board used for everything above.
`cycle_port.py 1-2 4 70 2 stop` (stop at first BOOTROM):

**19/20, BOOTROM on cycle 20** (`results/t2-hubB-port4-jack4a-until-bootrom.txt`).

Summary of every port-power cycle run with the same Adalogger (CP 11.0.0-alpha.1):

| hub | hub power | BOOTROM boots |
|---|---|---|
| Port Authority A | USB-C + USB 2 A adapter on barrel | 7/70 |
| Port Authority A | USB-C only | 0/30 |
| Port Authority A | USB-C + 4 A barrel supply | 1/6 (run aborted) |
| **Port Authority B** | USB-C + 4 A barrel supply | **1/20** |
| Realtek `1-6.3` | its own supply | 0/30 |

- **The problem follows to a second Rev C board**, so it is the design (or
  both boards equally), not one bad assembly.
- A stiffer 4 A supply did not fix it.
- The only clean Port Authority run is USB-C only (0/30, about 4% likely by
  chance at a 10% rate). Firming that up on hub B is the next discriminator:
  if USB-C only stays clean over 45+ cycles, the external power input path
  (eFuse, TPS2117 switchover) is implicated.

### Multi-board round-robin on hub B (4 A barrel supply), 2026-09-27

`cycle_ports.py` (one port at a time, stop each port at first failure).
Boards: port 1 Feather RP2040 (HID only, checked by VID:PID), port 2 Feather
RP2350 (REPL), port 3 Feather ESP32 V2 (CH9102 bridge, REPL), port 4
Adalogger (REPL, STEMMA QT cable to hub STEMMA1). None have batteries.

| port | board | result |
|---|---|---|
| 1 | Feather RP2040 | 15 + 19 passes, no failure (two runs, stopped by hand) |
| 2 | Feather RP2350 | 15 + 18 passes, no failure |
| 3 | Feather ESP32 V2 | fails round 1 in both runs: never leaves the bus in the 2 s off, REPL no answer after 10 s / 20 s settle. Answers normally when checked by hand afterwards. Unexplained |
| 4 | Adalogger | 3 passes, BOOTROM on round 4 |

Files: `results/t2-hubB-3feathers-roundrobin.txt` (stopped at round 15),
`results/t2-hubB-4feathers-roundrobin.txt` (stopped at round 19).

### New hypothesis: STEMMA QT back-feed into the unpowered controller

Re-reading the runs, the Adalogger's STEMMA QT cable was **off** for both clean
runs (Realtek 0/30; hub A USB-C only 0/30, confirmed by the "No pull up found"
error right after) and **connected** for every run with BOOTROM boots. The
barrel jack changed at the same time as the cable, so the earlier "external
power" conclusion is confounded.

Mechanism from the Rev C schematic: Q2 (BSS138DW) gates tie to the hub's
3.3 V; hub-side SDA/SCL pull up to 3.3 V through R5 (10K); QT-side SDA_QT/SCL_QT
pull up through R5 (10K) to `VCC`, which is STEMMA V+, i.e. the controller's
own 3.3 V rail. With port 4 off, SDA_QT/SCL_QT fall, the FETs conduct, and the
hub's 3.3 V feeds the Adalogger's 3.3 V rail through about 10K + 10K per line
(plus the RP2040 pin clamp diodes). The rail would not reach 0 V during
"off"; a flash chip that never sees a full power-down may not be ready at the
next boot and the RP2040 falls back to the ROM bootloader. Unmeasured.

Tests: (1) meter on the Adalogger 3V pin with port 4 held off, cable in vs
out; (2) cycle port 4 to first BOOTROM with the cable unplugged.

### Back-feed measured, 2026-09-27: CONFIRMED

Port 4 held off (`0000 off`, Adalogger gone from the bus), meter on the
Adalogger 3V pin to GND:

| STEMMA QT cable Adalogger to hub STEMMA1 | 3V pin with its port off |
|---|---|
| connected | **0.98 V** |
| unplugged | about 0 V ("nothing") |

The hub back-feeds an unpowered controller's 3.3 V rail through the STEMMA QT
lines. Still to show: that removing the cable removes the BOOTROM boots
(cycle test with the cable unplugged).

### Cable-unplugged cycle test, hub B, 4 A barrel supply: 70/70, CONFIRMED

`cycle_port.py 1-2 4 70 2 stop` with the STEMMA QT cable unplugged from the
Adalogger: **70/70 pass, 0 BOOTROM** (`results/t2-hubB-port4-nostemma-until-bootrom.txt`).

With the cable connected the same board and port ran about 1 in 10 BOOTROM.
0 in 70 at a 10% rate would happen by chance 0.9^70, about 0.06%.

Conclusion: the BOOTROM boots are caused by the STEMMA QT back-feed (0.98 V
on the unpowered Adalogger's 3.3 V rail), not by the hub's port switching or
its power input. Guide note: power the I2C controller from a supply that
stays on (a port that is never switched, or separate USB) when it is wired to
STEMMA QT.

## ESP32 V2 "never leaves the bus": host-side, not the board, 2026-09-28

Fresh flash first (2026-09-27): backup of all 59 files over the REPL
(`esp32v2-backup-20260927/`, sizes match), then esptool 5.4.0 (installed to
`~/esptool-lib` on bene, `PYTHONPATH=~/esptool-lib python3 -m esptool`)
`write-flash --erase-all` of CircuitPython 11.0.0-alpha.1 (sha256
`38cde549...a5f1`), chip ESP32-PICO-V3-02, MAC e8:9f:6d:31:9e:54, hash
verified, then a uhubctl power cycle of the port to boot. REPL then answers
and reports POWER_ON every cycle, but the device still never left the bus
during off, so every cycle counted as a fail.

Measured, layout: ESP32 V2 alone on hub port 1, Adalogger controller plugged
straight into bene (`1-1`, `PA_CTRL=1-1`), hub on the 4 A barrel supply:

| state | port 1 VBUS (INA ch1) | current | kernel still lists `1-2.1` |
|---|---|---|---|
| port 1 on | 5.105 V | 49.3 mA (ESP32 V2 idle) | yes |
| port 1 off 3 s | **0.000 V** | 0.0 mA | **yes** |

Also: `1-2.3` (with ttyACM4) was still listed a day after port 3 was switched
off and the board physically moved to port 1.

So VBUS is really cut and the board is really off; Linux just never processes
the disconnect. Hypothesis: with `-S` uhubctl switches power with a raw USB
request instead of the kernel's per-port `disable` file (which we have no
write permission for, see bene-setup.md), so the kernel is not told. Native
USB CircuitPython boards are removed anyway because their interfaces are
polled and error out; the CH9102 is idle while its tty is closed. Fix to
test: udev rule making `*-port*/disable` writable by plugdev, drop `-S`.

### Resolved, 2026-09-28: uhubctl `-S` hides the disconnect from the kernel

Controller Adalogger straight into bene (`1-1`, `PA_CTRL=1-1`), no STEMMA QT
back-feed path. ESP32 V2 alone on hub port 1, 4 A barrel supply.

With `-S` (raw hub request, kernel not told):

| port 1 | VBUS (INA ch1) | current | `1-2.1` in sysfs |
|---|---|---|---|
| on | 5.103 V | 50.2 mA | yes, devnum 10 |
| off 3 s | 0.000 V | 0.0 mA | **yes** |
| on again | 5 V | | devnum 11 |

`journalctl -k` logs `usb 1-2.1: USB disconnect, device number 10` at the
moment power comes back, not at power off. The board is really cycled every
time; Linux only learns of it on the reconnect. This is documented uhubctl
behavior ("USB devices are not removed after port power down on Linux"); the
fix for kernel 6.0+ is to let uhubctl write the per-port `disable` files.

Fix: udev rule from uhubctl's own `52-usb.rules`, added to
`/etc/udev/rules.d/52-uhubctl.rules` (see `bene-setup.md`). Port `disable`
files now `root dialout 660`. Without `-S`:

| port 1 | VBUS | current | `1-2.1` in sysfs | tty |
|---|---|---|---|---|
| on | 5.104 V | 49.4 mA | yes, devnum 11 | yes |
| off 3 s | 0.000 V | 0.0 mA | **gone** | **gone** |
| on again | 5.104 V | 49.4 mA | devnum 12 | ttyACM0 |

The kernel logs the disconnect at power off. The stale `1-2.3` left from
09-27 cleared after one on/off of the empty port 3 without `-S`.

`-S` removed from `cycle_port.py` and `cycle_ports.py`.
`cycle_ports.py 1-2 1 10 2 10` (`results/t2-port1-esp32v2-nosysS-10x.txt`):
**10/10 PASS**, `off=0000`, gone after 0.00 s, back within 0.4 s, POWER_ON
every cycle.

Conclusion: the ESP32 V2 "never leaves the bus" was a host setup issue, not
the hub or the board. Guide note: install the `disable` rule and do not use
`-S`, otherwise boards behind USB-UART bridges stay listed while off.

### Fix confirmed: udev rule for the per-port `disable` files, 2026-09-28

Rule added to `/etc/udev/rules.d/52-uhubctl.rules` (by hand, sudo):

```
SUBSYSTEM=="usb", DRIVER=="hub|usb", RUN+="/bin/sh -c \"chown -f root:dialout $sys$devpath/*port*/disable || true\"", RUN+="/bin/sh -c \"chmod -f 660 $sys$devpath/*port*/disable || true\""
```

Hub moved to bene root port 1 (`1-1`). `1-1-port*/disable` now
`root:dialout 660`. uhubctl without `-S` uses sysfs, no permission warning.
ESP32 V2 on port 4: gone from the bus **5 ms** after power-off, kernel logs
the disconnect immediately. `cycle_ports.py 1-1 4`: 3/3 pass (stopped by hand,
`results/t2-hubB-esp32v2-sysfs.txt`). All scripts now call uhubctl without `-S`.

## T5. Current monitoring, channel map, 2026-09-28: PASS

Hub `1-1` on the 4 A barrel supply. Port 1 Feather M0, port 2 Feather RP2350,
port 3 Feather RP2040, port 4 ESP32 V2. Controller Adalogger on the Realtek
hub (`PA_CTRL=1-6.3.4.1`), STEMMA QT to hub STEMMA1. `ina_channel_map.py`
(`results/t5-channel-map.txt`):

```
all on         ch1: 5.096 V    6.4 mA  ch2: 5.096 V   20.4 mA  ch3: 5.096 V   25.2 mA
port 1 off     ch1: 0.000 V    0.0 mA  ch2: 5.096 V   20.4 mA  ch3: 5.096 V   25.2 mA
port 2 off     ch1: 5.104 V    6.4 mA  ch2: 0.000 V    0.0 mA  ch3: 5.096 V   25.2 mA
port 3 off     ch1: 5.104 V    6.4 mA  ch2: 5.104 V   20.4 mA  ch3: 0.000 V    0.0 mA
port 4 off     ch1: 5.110 V    6.4 mA  ch2: 5.104 V   20.5 mA  ch3: 5.104 V   25.2 mA
```

- Channel N = port N for 1-3; port 4 unmonitored, as designed.
- No crosstalk: switching a port off changes only its own channel.
- Idle currents: Feather M0 6.4 mA, RP2350 20.4 mA, RP2040 25.2 mA
  (0.4 mA resolution). Accuracy vs a USB meter not yet checked.

## T9a. DIP mode USB (SW2 `0 0 0 1`), 2026-09-29: PASS

DIP 4 on, 1-3 off, SW1 reset. Hub `1-1` still on the 4 A barrel supply.
`results/t9-dip-0001-lsusb.txt`:

| | EXT `0 0 0 0` (T1) | USB `0 0 0 1` |
|---|---|---|
| bmAttributes | `0xe0` Self Powered, Remote Wakeup | `0xa0` Bus Powered, Remote Wakeup |
| MaxPower | 2 mA | 100 mA |
| Hub status | Self Powered | Bus Powered |
| wHubCharacteristic | `0x0009` per-port power, per-port OC | same |

- DIP 4 is read at reset (SW1) as designed. The "always Self Powered"
  result from T1 is the EXT mode default, not a fault: USB mode fixes it.
- Per-port switching unchanged: port 3 RP2040 3/3 `POWER_ON`
  (`results/t9-dip-0001-cycle.txt`).
- Port 1 Feather M0 read `UNKNOWN` 3/3 while cycling cleanly (off `0000`,
  gone, back in 1.3 s). Not a hub fault: atmel-samd
  `common_hal_mcu_processor_get_reset_reason()` always returns
  `MCU_RESET_REASON_UNKNOWN`. `cycle_port.py` needs an enum-style check for
  SAMD boards.

## T9b/T9c. DIP modes SMBUS (`1 1 1 0`) and EEPROM (`1 1 1 1`), 2026-09-29: PROBLEM, parked

Controller Adalogger on `PA_CTRL=1-6.3.4.1`, STEMMA1. Datasheet saved as
`design/USB251xB-datasheet-DS00001692C.pdf`.

| | SMBUS `1 1 1 0` (4 resets) | EEPROM `1 1 1 1` (1 reset) |
|---|---|---|
| Hub on USB | no | no |
| Kernel at reset release | 4x `new low-speed USB device`, `error -71`, gives up | same |
| I2C scan | 0x40, 0x50-0x57; no 0x2C | same |
| Block read 0x2C reg 0x00 | `OSError 19` | same |
| Bus after a quiet reset | idle (`11`) | idle |

- Datasheet: in SMBus mode the hub "waits indefinitely" at 0x2C (5.3, 5.3.1).
  The t5 1000 ms is a timing span, not a timeout. `smbus_race.py` probed
  every ~56 ms across a reset: 1073 tries, 0 ACK. No early window.
- Probing during reset release left SCL held low (`i2c_lines.py`: `01`
  x20); a quiet reset cleared it. Linux `usb251xb.c` warns that bus
  activity at reset release can mislatch CFG_SEL0 (shared SCL pin).
- The config EEPROM is blank (`eeprom_dump.py`: 256 x `0xFF`,
  `results/t9-eeprom-dump.txt`).
- Working theory, unconfirmed: `1 1 1 0` latches EEPROM mode (11), not
  SMBus. A blank EEPROM loads register 0xFA = `0xFF`, and bit 0 swaps
  upstream D+/D- (datasheet 5.1.29), which a host sees as a low-speed
  device. `1 1 1 1` matching `1 1 1 0` exactly supports this. Open: why
  CFG_SEL1 reads high with DIP 4 off (R6 100K pulldown; `0 0 0 0` read low).
- Not run: `0 1 1 0` (EEPROM unpowered) to separate the two latch cases.
- Schematic review: no SDA/SCL swap, strap nets match the DIP table, RESET_N
  is SW1 switching between supervisor `APX_OUT` and GND, no RC.
- Guide note: EEPROM mode is unusable until the EEPROM is programmed; SMBus
  mode unverified. Scripts: `smbus_probe.py`, `smbus_race.py`,
  `eeprom_dump.py`, `i2c_lines.py`.

## T13. SWD through the hub, Feather RP2350 on port 2, 2026-09-29: PASS

Hub `1-1`, DIP `0 0 0 0`, 4 A barrel. Raspberry Pi Debug Probe
(`2e8a:000c`) on the Realtek hub, always powered, SWD lead to the RP2350.
Stock openocd 0.12.0 on bene has no `rp2350.cfg`; used the raspberrypi fork
(`0.12.0+dev-g098b86f`) copied from bravo to `~/.local/openocd-rp2350`, runs
unchanged on Ubuntu 26.04. Probe is `root:plugdev`, no sudo.

`swd_port.sh 1-1 2` (`results/t13-swd-port.txt`):

- Port on: `SWD DPIDR 0x4c013477`, both Cortex-M33 examined at 5 MHz.
- Port off: `Error connecting DP: cannot read IDR`. SWD works as a power check.
- Port on, `reset halt`: both cores halted, `pc 0x00000088` (boot ROM);
  `resume` returns CircuitPython to USB.

Back-feed check with the probe powered and connected while the port is off:
`cycle_ports.py 1-1 2 30 2 10`, **30/30 `POWER_ON`**, back in 1.5-1.6 s, no
bootloader boots (`results/t13-rp2350-probe-cycles.txt`). Unlike the STEMMA
QT cable on the Adalogger, the Debug Probe does not keep this board alive.

## T13b. Flash the Feather RP2350 over SWD through the hub, 2026-09-29: PASS

Same setup as T13. Board had CircuitPython 11.0.0-alpha.1 plus user files.

1. Backup: CIRCUITPY copied to `rp2350-backup-20260929/`, 72 files md5
   verified (`rp2350-backup-20260929.md5`).
2. Firmware: official `adafruit-circuitpython-adafruit_feather_rp2350-en_US-11.0.0-alpha.1.uf2`
   converted to a raw bin on bene (`~/fw/fw.bin`): family `0xe48bff59`
   (RP2350 ARM), `0x10000000`-`0x100c3000`, 798720 bytes.
3. `openocd ... -c "program fw.bin 0x10000000 verify reset exit"` with the
   raspberrypi fork: flash detected as W25Q64 8 MiB, erase `0x0`-`0xc2fff`
   only, `Verified OK`, 17 s total (`results/t13-swd-flash.txt`).
4. After reset: back on USB as Feather RP2350, `boot_out.txt` 11.0.0-alpha.1,
   all 72 files match the backup md5. The filesystem is outside the erased range.

- The Debug Probe runs old firmware 1.0.1; openocd warns and uses a
  low-performance workaround. Updating the probe would speed this up.
- UF2 to bin conversion is inline Python in the session; worth a
  `uf2_to_bin.py` in `test-scripts/` if this goes in the guide.

## Debug Probe firmware update 1.0.1 -> 2.3.1, 2026-09-30: done

Probe `E6647C740321342C` at `1-6.3.1` (Realtek hub).

- No remote route to BOOTSEL on 1.0.1: a 1200-baud touch on its CDC
  (`6.3.1:1.1`) did nothing, and it has no USB reset interface for
  `picotool reboot` (only CMSIS-DAP v2 vendor interface plus CDC). Manual
  BOOTSEL (case lid off, hold button, replug).
- `debugprobe.uf2` from raspberrypi/debugprobe `debugprobe-v2.3.1`
  (family `0xe48bff56`, RP2040), copied to `RPI-RP2` via `gio mount`.
- After: `2e8a:000c`, bcdDevice `2.31`, same serial. openocd no longer
  prints the old-firmware warning; RP2350 attach OK (DPIDR `0x4c013477`).
- v2.3.1 still exposes no reset interface, so the next update also needs
  the button.

## T13c. SWD reflash timing after the probe update, 2026-09-30: PASS

Same image and command as T13b. Files md5-checked against the backup before
and after. `results/t13-swd-flash-dp231.txt`:

| Probe firmware | openocd warning | program + verify + reset |
|---|---|---|
| 1.0.1 | old firmware, low-performance workaround | 17 s (whole seconds) |
| 2.3.1 | none | 11.2 s |

## T4/T12. STEMMA2 pass-through and I2C OLED status display, 2026-09-30: PASS

Adafruit 326 (0.96" 128x64 SSD1306, 0x3D) on hub STEMMA2. Controller
Adalogger (`PA_CTRL=1-6.3.4.1`) on STEMMA1, DIP `0 0 0 0`.

Display, from the product page (adafruit.com/product/326, read 2026-09-30):

| | |
|---|---|
| Product | Monochrome 0.96" 128x64 OLED Graphic Display - STEMMA QT, PID 326 |
| Resolution | 128 x 64, monochrome |
| Controller | SSD1306 (confirmed by working with `adafruit_displayio_ssd1306`; the page text loaded did not name it) |
| I2C address | 0x3C-0x3D by jumper; this unit 0x3D (scan) |
| Connectors | 2x STEMMA QT; I2C default; auto-reset, RESET pin optional |
| PCB | 29.2 x 26.7 mm, mounting holes 24 mm apart |
| Screen | 26.6 x 19 mm |
| Thickness / weight | 6.2 mm / 4.5 g |

Adafruit 938 (1.3" 128x64) should run the same code if it is also SSD1306 at
0x3D; not checked or tested here.

- STEMMA2 pass-through: scan `['0x3d', '0x40']`, OLED on the same bus as
  the INA3221 (`results/t4-stemma2-scan.txt`).
- Libraries from the 11.x mpy bundle (20260930): `adafruit_displayio_ssd1306`,
  `adafruit_display_text`. CP 11 uses `i2cdisplaybus.I2CDisplayBus`.
- `controller/oled_ports.py` as `code.py`: ports 1-3 V and mA from INA3221
  registers, port 4 "(no INA)". Port 1 off for 10 s: P1 read `0.00V`
  (confirmed by eye).
- Port 4 state is not visible to the controller (no INA channel, port power
  not on I2C), so the host pushes it: `oled_push.py` sends `PA xxxx` from
  uhubctl every second over the controller's USB serial; stale after 5 s
  shows `?`. `oled_demo.sh 1-1 "4 2" 10`: port 4 and port 2 off/on each
  showed on the OLED within about a second (`results/t12-oled-push.txt`).
