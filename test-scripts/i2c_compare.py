"""T4 debug: INA3221 register reads via board.STEMMA_I2C() vs a fresh busio.I2C.

usage: python3 i2c_compare.py [hub_path] [controller_port] [reads]    default 1-2 4 10
Each case prints ok/err counts for writeto_then_readfrom(0x40, [0xFE]).
A failing read takes the 1 s RP2040 bus timeout, so a bad case is slow.
"""
import sys
from repl import Repl, by_path

args = sys.argv[1:] + ["1-2", "4", "10"][len(sys.argv) - 1:]
r = Repl(by_path(args[0], args[1]))
print("synced:", r.sync())
print(r.paste(f"""
import board, busio
def reads(i, label, n={args[2]}):
    b = bytearray(2); ok = err = 0; last = None
    while not i.try_lock():
        pass
    try:
        for _ in range(n):
            try:
                i.writeto_then_readfrom(0x40, bytes([0xFE]), b); ok += 1
            except OSError as e:
                err += 1; last = e
    finally:
        i.unlock()
    print("CASE", label, "ok", ok, "err", err, b.hex(), last)
i = board.STEMMA_I2C(); reads(i, "A STEMMA_I2C as found")
i = board.STEMMA_I2C(); reads(i, "B STEMMA_I2C again")
i.deinit(); i = board.STEMMA_I2C(); reads(i, "C deinit, STEMMA_I2C new")
i.deinit(); i = busio.I2C(board.SCL, board.SDA); reads(i, "D busio.I2C 100k")
i.deinit(); i = busio.I2C(board.SCL, board.SDA, frequency=400000); reads(i, "E busio.I2C 400k")
i.deinit(); i = board.STEMMA_I2C(); reads(i, "F STEMMA_I2C after busio")
""", wait=120))
r.close()
