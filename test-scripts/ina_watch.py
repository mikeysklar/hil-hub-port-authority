"""T6: watch one port's voltage and current per second while it powers a load.

usage: python3 ina_watch.py [hub] [port] [seconds] [on_after_s] [tag]    default 1-1 1 90 2 run
Switches <port> (1-3) off, starts the watch, switches it on after on_after_s,
and prints one line per second: bus volts min/avg and current min/avg/max.
on_after_s < 0 watches only: the port is not switched (load already running).
For over-current tests: the AP22653 limit on this board is about 1.0 A
(RLIM 25.5 kOhm), so a load held in limit shows max near 1000 mA and a
sagging bus voltage. Controller: PA_CTRL=<usb path>, or hub port 4.

INA3221 set to the one channel, shunt + bus continuous, 1.1 ms conversions,
no averaging (config 0x4127 / 0x2127 / 0x1127), restored to 0x7127 at the end.
Output also goes to ../results/watch-<tag>-p<port>.txt.
"""
import subprocess, sys, threading, time
from repl import Repl, ctrl_tty

args = sys.argv[1:] + ["1-1", "1", "90", "2", "run"][len(sys.argv) - 1:]
hub, port, secs, on_after, tag = args[0], int(args[1]), int(args[2]), float(args[3]), args[4]
assert 1 <= port <= 3, "only ports 1-3 have an INA3221 channel"
UH = ["/usr/sbin/uhubctl", "-l", hub, "-p", str(port)]
cfg = {1: 0x4127, 2: 0x2127, 3: 0x1127}[port]
sh, bus = 2 * port - 1, 2 * port

r = Repl(ctrl_tty(hub, "4"))
print("synced:", r.sync())
print(r.paste(f"""
import board, busio, time
try:
    i2c.deinit()
except Exception:
    pass
try:
    board.STEMMA_I2C().deinit()
except Exception:
    pass
i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
b = bytearray(2)
def rd(reg):
    i2c.writeto_then_readfrom(0x40, bytes([reg]), b)
    v = (b[0] << 8) | b[1]
    return (v - 0x10000 if v & 0x8000 else v) >> 3
def wr(reg, val):
    i2c.writeto(0x40, bytes([reg, val >> 8, val & 0xFF]))
while not i2c.try_lock():
    pass
wr(0x00, {cfg})
i2c.unlock()
def watch(secs):
    while not i2c.try_lock():
        pass
    try:
        t0 = time.monotonic()
        for s in range(secs):
            n = 0; vmin = 99.0; vsum = 0.0; imin = 9999.0; imax = -9999.0; isum = 0.0
            while time.monotonic() - t0 < s + 1:
                v = rd({bus}) * 0.008
                i = rd({sh}) * 0.4
                n += 1; vsum += v; isum += i
                vmin = min(vmin, v); imin = min(imin, i); imax = max(imax, i)
            print("W %3d n=%4d  V min %5.3f avg %5.3f  mA min %7.1f avg %7.1f max %7.1f" %
                  (s, n, vmin, vsum / n, imin, isum / n, imax))
    finally:
        i2c.unlock()
    print("WATCH DONE")
print("READY")
""", wait=10))

lines = []
try:
    if on_after >= 0:
        subprocess.run(UH + ["-a", "off", "-r", "30", "-w", "500"], capture_output=True)
        time.sleep(2)
    r.s.reset_input_buffer()
    r.s.write(f"watch({secs})\r".encode())
    t = threading.Timer(max(on_after, 0), lambda: on_after >= 0 and (
        subprocess.run(UH + ["-a", "on"], capture_output=True),
        print(time.strftime("%T"), f"port {port} switched on", flush=True)))
    t.start()
    buf = ""
    t_end = time.time() + secs + 20
    while time.time() < t_end and "WATCH DONE" not in buf:
        chunk = r.s.read(4096).decode(errors="replace")
        buf += chunk
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            if line.startswith("W "):
                print(time.strftime("%T"), line.strip(), flush=True)
                lines.append(line.strip())
    t.join()
finally:
    r.read_until_prompt(5)
    print(r.paste("while not i2c.try_lock():\n    pass\nwr(0x00, 0x7127)\ni2c.unlock()\ni2c.deinit()\nprint('INA3221 config restored')", wait=5))
    r.close()
    with open(f"../results/watch-{tag}-p{port}.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
