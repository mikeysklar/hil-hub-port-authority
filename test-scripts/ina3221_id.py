"""T4: confirm the device at 0x40 is an INA3221 by its ID registers (read only).

usage: python3 ina3221_id.py [hub_path] [controller_port] [addr]    default 1-2 4 0x40
Expect 0xFE = 5449 ("TI"), 0xFF = 3220 (INA3221), 0x00 = 7127 at power-on.
Each read is retried up to 5 times and every ETIMEDOUT is printed (T4 open item).
"""
import sys
from repl import Repl, by_path, ctrl_tty

args = sys.argv[1:] + ["1-2", "4", "0x40"][len(sys.argv) - 1:]
hub, port, addr = args[0], args[1], int(args[2], 0)
r = Repl(ctrl_tty(hub, port))
print("synced:", r.sync())
out = r.paste(f"""
import board
i2c = board.STEMMA_I2C()
b = bytearray(2)
for reg in (0xFE, 0xFF, 0x00):
    for _ in range(5):
        while not i2c.try_lock():
            pass
        try:
            i2c.writeto_then_readfrom({addr}, bytes([reg]), b)
            print("REG", hex(reg), b.hex())
            break
        except OSError as e:
            print("ERR", hex(reg), e)
        finally:
            i2c.unlock()
""", wait=30)
print("\n".join(l for l in out.splitlines() if l.startswith(("REG", "ERR", "Trace", "  File")) or "Error" in l))
r.close()
