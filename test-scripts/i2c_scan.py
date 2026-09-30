"""T4: scan the hub's I2C bus from a CircuitPython controller on a hub port.

usage: python3 i2c_scan.py [hub_path] [controller_port]    default 1-2 4
Expect 0x40 (INA3221) with DIP 2/3 off; 0x50 / 0x2C appear only with DIP 2/3 on.
"""
import sys
from repl import Repl, by_path, ctrl_tty

args = sys.argv[1:] + ["1-2", "4"][len(sys.argv) - 1:]
r = Repl(ctrl_tty(args[0], args[1]))
print("synced:", r.sync())
r.run("import board; i2c = board.STEMMA_I2C()")
print(r.run("i2c.try_lock(); print([hex(a) for a in i2c.scan()]); i2c.unlock()"))
r.close()
