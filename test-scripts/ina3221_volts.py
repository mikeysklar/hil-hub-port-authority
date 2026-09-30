"""T5/T8: read INA3221 bus voltage and shunt current on channels 1-3 (ports 1-3).

usage: python3 ina3221_volts.py [hub_path] [controller_port] [samples]    default 1-2 4 10
Raw register reads, no library. Bus voltage: reg 0x02/0x04/0x06, bits 15:3,
8 mV/LSB. Shunt voltage: reg 0x01/0x03/0x05, bits 15:3, 40 uV/LSB, signed.
Current = shunt / 0.1 ohm (R8, R16, R24). Default config 0x7127 = continuous,
all channels, so no configuration write is needed.
"""
import sys
from repl import Repl, by_path, ctrl_tty

args = sys.argv[1:] + ["1-2", "4", "10"][len(sys.argv) - 1:]
r = Repl(ctrl_tty(args[0], args[1]))
print("synced:", r.sync())
out = r.paste(f"""
import board, time
i2c = board.STEMMA_I2C()
b = bytearray(2)
def reg(n):
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto_then_readfrom(0x40, bytes([n]), b)
    finally:
        i2c.unlock()
    v = (b[0] << 8) | b[1]
    return v - 0x10000 if v & 0x8000 else v
rows = []
for _ in range({args[2]}):
    row = []
    for ch in range(3):
        bus = (reg(2 + 2 * ch) >> 3) * 0.008
        shunt = (reg(1 + 2 * ch) >> 3) * 40e-6
        row.append((bus, shunt / 0.1 * 1000))
    rows.append(row)
    time.sleep(0.1)
for ch in range(3):
    v = [r[ch][0] for r in rows]; i = [r[ch][1] for r in rows]
    print("CH%d port%d bus V min %.3f avg %.3f max %.3f | mA min %.1f avg %.1f max %.1f" % (
        ch + 1, ch + 1, min(v), sum(v) / len(v), max(v), min(i), sum(i) / len(i), max(i)))
""", wait=30)
print("\n".join(l for l in out.splitlines() if l.startswith(("CH", "Trace", "  File")) or "Error" in l))
r.close()
