"""T9b: probe the USB2514B SMBus port (0x2C) with real register reads.

usage: python3 smbus_probe.py [hub_path] [controller_port]    default 1-2 4
Needs DIP 1 2 3 on, 4 off (SMBUS mode) and a hub reset. The hub waits off USB
until a controller configures it. A 0-byte scan may not see it, so this tries
a block read of the VID/PID registers (0x00-0x03) as well as a probe.
"""
import sys
from repl import Repl, ctrl_tty

args = sys.argv[1:] + ["1-2", "4"][len(sys.argv) - 1:]
r = Repl(ctrl_tty(args[0], args[1]))
print("synced:", r.sync())
print(r.paste("""
import board
i2c = board.STEMMA_I2C()
while not i2c.try_lock():
    pass
try:
    print("scan", [hex(a) for a in i2c.scan()])
    for addr in (0x2C, 0x2D):
        b = bytearray(5)
        try:
            i2c.writeto_then_readfrom(addr, bytes([0x00]), b)
            print(hex(addr), "block read 0x00:", [hex(x) for x in b])
        except Exception as e:
            print(hex(addr), "Error", repr(e))
finally:
    i2c.unlock()
    i2c.deinit()
""", wait=15))
r.close()
