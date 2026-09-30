"""Read the STEMMA I2C line levels on the controller (no pulls), to spot a held bus.

usage: python3 i2c_lines.py [hub_path] [controller_port] [samples]    default 1-2 4 20
Prints SCL/SDA as 1/0, sampled every 50 ms. 1 1 is an idle bus.
"""
import sys
from repl import Repl, ctrl_tty

args = sys.argv[1:] + ["1-2", "4", "20"][len(sys.argv) - 1:]
r = Repl(ctrl_tty(args[0], args[1]))
print("synced:", r.sync())
out = r.paste(f"""
import board, digitalio, time
scl = digitalio.DigitalInOut(board.SCL)
sda = digitalio.DigitalInOut(board.SDA)
s = ""
for i in range({args[2]}):
    s += "%d%d " % (scl.value, sda.value)
    time.sleep(0.05)
print("LINES scl,sda:", s)
scl.deinit()
sda.deinit()
""", wait=10)
print("\\n".join(l for l in out.splitlines() if l.startswith("LINES") or "Error" in l))
r.close()
