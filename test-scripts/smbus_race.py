"""T9b: does the USB2514B SMBus slave (0x2C) answer right after reset, then stop?

usage: python3 smbus_race.py [hub_path] [controller_port] [seconds]    default 1-2 4 60
DIP 1 2 3 on, 4 off (SMBUS). Start it, then slide SW1 off and back on while it runs.
The controller block-reads register 0x00 at 0x2C every 20 ms and prints each
change between ACK and NACK with a timestamp (ms since start).
  ACK early, then NACK: the hub leaves SMBus mode after a window.
  never ACK:            CFG_SEL latched wrong at reset (or something else).
Probing while RESET_N rises can itself mislatch CFG_SEL0 (it shares the SCL pin);
the 20 ms gaps keep SCL idle-high most of the time.
"""
import sys
from repl import Repl, ctrl_tty

args = sys.argv[1:] + ["1-2", "4", "60"][len(sys.argv) - 1:]
secs = int(args[2])
r = Repl(ctrl_tty(args[0], args[1]))
print("synced:", r.sync())
print(r.paste(f"""
import board, time
i2c = board.STEMMA_I2C()
while not i2c.try_lock():
    pass
b = bytearray(5)
t0 = time.monotonic_ns()
state = None
acks = 0
tries = 0
first = None
last = None
try:
    print("GO")
    while time.monotonic_ns() - t0 < {secs} * 1000000000:
        ms = (time.monotonic_ns() - t0) // 1000000
        try:
            i2c.writeto_then_readfrom(0x2C, bytes([0x00]), b)
            ok = True
        except OSError:
            ok = False
        tries += 1
        if ok:
            acks += 1
            last = ms
            if first is None:
                first = ms
        if ok != state:
            print(ms, "ACK" if ok else "NACK", [hex(x) for x in b] if ok else "")
            state = ok
        time.sleep(0.02)
finally:
    i2c.unlock()
    i2c.deinit()
print("tries", tries, "acks", acks, "first", first, "last", last)
""", wait=secs + 20))
r.close()
