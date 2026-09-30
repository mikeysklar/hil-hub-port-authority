# Port Authority (Smart HIL Hub Rev C): test plan

Design reference: `design/Smart HIL Hub Rev C.sch` at `461a9006b` (matches the
JLC order). Host: bene.local, hub at USB path `1-2`. Only touch hub `1-2`;
the `1-6` tree on bene has other boards on it.

Each test records command, verbatim output, pass/fail in `test-log.md`, and
the media listed for the guide in `media/`. Anything intermittent gets 10+
trials. Steps marked **[you]** are physical or need sudo.

## Equipment

| Item | Have? | Used by |
|---|---|---|
| Rev C hub on bene `1-2` | yes | all |
| Feather RP2040 Adalogger (CP 10.3.0) as I2C controller | yes | T4-T7, T11, T12 |
| STEMMA QT cable x2 | ? | T4, T11, T12 |
| STEMMA QT OLED (0x3C) | ? | T4, T12 |
| USB power meter (inline USB-A) | ? | T5 |
| Load: Smart HIL Load, or USB load resistor ~0.5 A and >1 A | ? | T5, T6 |
| Regulated 5 V supply, barrel 2.1 mm and bare leads | ? | T8 |
| Second Rev C hub | yes (9 spare) | T11 |
| Target boards for ports 1-3 | ? | T2, T16 |
| Raspberry Pi Debug Probe (on bene `1-6.3.1`) | yes | T16 |
| Mac with a free USB port | yes | T15 |

## Setup

S1. **[you]** Photo the DIP switch and note positions 1-4. Expected for
normal use: all off (CFG_SEL 00).
S2. **[you]** Move the Adalogger to **port 4** (unmonitored). Cable from
Adalogger STEMMA QT to hub STEMMA1.
S3. Update `uhubctl` status and the Adalogger's by-path tty in the notes
(`1-2.4`).

## T1. Enumeration and descriptors

`lsusb -v -d 0424:2514`, `uhubctl -l 1-2`, `lsusb -t`.

Pass: `0424:2514`, 4 ports, `ppps`, Multi-TT (`bDeviceProtocol 2`), and
self-powered bit in `bmAttributes` matches CFG_SEL (00 = self, 10 = bus).
Record whether `LOCAL_PWR` (only a 100K pull-down in Rev C) changes anything
when on external 5 V (cross-check in T8).

Media: terminal session.

## T2. Per-port power switching

For each port 1-4 with a target board: 10 cycles of off, check `0000 off` and
device gone, on, device back, REPL `reset_reason == POWER_ON`. Reuse
`cycle10.py` with the port and by-path tty parameterized. Use `-S`.

Control: one `microcontroller.reset()` per port must read `SOFTWARE`, proving
the check can fail.

Also: switching one port leaves the other three devices untouched (devnums
unchanged).

Pass: 40/40 plus controls. Media: terminal session, GIF of a board LED going
dark and back.

## T3. Settle time

Per port, 10 trials: time from `-a on` to (a) device on bus, (b) tty present,
(c) REPL answers, (d) CIRCUITPY mounted (bene desktop automount).

Pass: numbers only, report min/median/max. Feeds the "wait N seconds" advice
in the guide.

## T4. I2C bus and STEMMA pass-through

From the Adalogger REPL: `board.STEMMA_I2C()` scan.

| DIP state | Expected addresses |
|---|---|
| 2, 3 off | 0x40 (INA3221) only |
| 2, 3 on, 1 on | 0x40, 0x50 (EEPROM), 0x2C only if in SMBus mode |

Then plug the OLED into hub **STEMMA2**: 0x3C appears. Proves the pass-through.

Media: photo of cabling, terminal session.

## T5. Current monitoring (INA3221)

1. Channel map: load on port 1, see which channel moves; repeat ports 2, 3.
   Port 4 must show nothing on any channel.
2. Accuracy: idle target board, then ~0.5 A load, INA3221 vs USB power meter,
   each port. 10 readings each.
3. Port off: channel reads ~0 mA.
4. Bus voltage per channel, idle and loaded (shunt is 0.1 ohm, expect about
   0.05 V drop at 0.5 A).

Library: `adafruit_ina3221`. Pass: channel map documented, readings within
meter tolerance plus INA spec. Media: code block, terminal session, photo.

## T6. LEDs and over-current

1. Green follows uhubctl on/off, each port. GIF.
2. **Gated, ask first:** >1 A load on one port. Expect AP22653 limit, red LED,
   `uhubctl` port status shows over-current, other ports unaffected. Only with
   a defined load, never a short, and never above ~4 A total.

## T7. Hub reset (SW1 and JP1)

SW1 to hold: hub and all downstream drop off the bus; back to run: all return.
JP1 pad to GND briefly: same. Needed later to latch DIP changes.

Media: terminal session showing `lsusb -t` before/during/after.

## T8. Power input

1. USB-only: all 4 ports on with loads, measure VBUS at a port.
2. **[you]** 5 V on the DC jack: re-run T1 `bmAttributes`, measure port VBUS.
   Terminal block the same.
3. Hot switch-over: remove external 5 V while boards run on ports. Do targets
   brown out or ride through?

Pass: behavior documented. UVLO/OVLO threshold tests only with an adjustable
supply, optional.

## T9. DIP configuration modes

Latch each with SW1 reset. Back up EEPROM before any write.

| Mode | SW2 | Test |
|---|---|---|
| 00 default | all off | baseline, done in T1 |
| 10 bus-powered | 4 on | `bmAttributes` shows bus-powered |
| 11 EEPROM | 1, 2, 3, 4 on | read EEPROM (0x50) from Adalogger, save image. If blank, write a config with custom product string, reset, confirm in `lsusb -v` |
| 01 SMBus | 2, 3 on | hub stays off the bus until configured. Write registers + attach at 0x2C from Adalogger, confirm enumeration |

Note: in 01 and 11 the Adalogger shares the bus with the hub at reset time.
Keep it idle on the bus during hub reset.

Media: code blocks for EEPROM read/write and SMBus attach, terminal sessions.

## T10. JST-XH port and upstream headers (optional)

Continuity check of one port XH against its USB-A. Document pinout, with the
footprint quirk that schematic pin 1 is JST wire 4.

## T11. Chaining

1. USB cascade: second hub into port 3. `uhubctl` shows `1-2.3` as a hub;
   switch a port on it; switch port 3 on the first hub and the whole second
   hub drops.
2. I2C chain: first hub STEMMA2 to second hub STEMMA1. Scan shows two 0x40
   devices colliding. **[you]** bridge A0 on the second hub, scan shows 0x40
   and 0x41. Read both INA3221s.

Media: photo of two hubs, terminal sessions.

## T12. Display

OLED on STEMMA2, `code.py` on the Adalogger showing per-port mA and on/off.
GIF while uhubctl switches ports 1-3.

Media: code block, GIF.

## T13. SWD / openocd through the hub

1. Debug Probe (bene `1-6.3.1`) SWD to a target on a hub port.
2. Workflow: `uhubctl` cycle the target, openocd attach, halt, read a
   register, resume. Also the recovery loop: a wedged target is recovered by
   port power cycle alone.
3. Board-specific notes table from `mounted-hil-farm/FARM-REFERENCE.md`:
   RP2040, RP2350, SAMD21/51, nRF52840, STM32F405, ESP32-S2/S3. Mark which
   were exercised on this hub vs carried over from bravo.

Media: terminal sessions, photo of probe wiring.

## T14. macOS

1. `brew install uhubctl`. Hub on the Mac directly.
2. `uhubctl` list, switch port 1 off/on, 10 cycles with a board attached.
3. Record: sudo needed or not, whether the Mac re-enumerates cleanly, any
   `-S`/libusb messages, Apple Silicon quirks.

Media: terminal session.

## T15. Linux host setup page

Reproduce `bene-setup.md` as the guide's setup page, with the single-line
udev rule and a note on the sysfs `disable` permission warning and `-S`.

## Order

S1-S3, T1, T7, T2, T3, T4, T5, T12, T6, T8, T9, T11, T13, T14, T10, T15.
Read-only and low-risk first; over-current, power input and EEPROM writes last.
