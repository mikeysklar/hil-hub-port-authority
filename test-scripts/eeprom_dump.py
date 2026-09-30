"""T9: read-only dump of the hub config EEPROM (24LC02, 256 bytes at 0x50).

usage: python3 eeprom_dump.py [hub_path] [controller_port]    default 1-2 4
Needs DIP 1 2 3 on (EEPROM powered and connected). Never writes.
"""
import re, sys
from repl import Repl, ctrl_tty

args = sys.argv[1:] + ["1-2", "4"][len(sys.argv) - 1:]
r = Repl(ctrl_tty(args[0], args[1]))
print("synced:", r.sync())
out = r.paste("""
import board
i2c = board.STEMMA_I2C()
while not i2c.try_lock():
    pass
try:
    for base in range(0, 256, 16):
        b = bytearray(16)
        i2c.writeto_then_readfrom(0x50, bytes([base]), b)
        print("EE %02x:" % base, " ".join("%02x" % x for x in b))
finally:
    i2c.unlock()
    i2c.deinit()
""", wait=10)
print("\n".join(l for l in out.splitlines() if l.startswith("EE") or "Error" in l))
r.close()
