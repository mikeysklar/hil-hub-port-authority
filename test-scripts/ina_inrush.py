"""T5/T11: capture a board's power-on current on hub ports 1-3 with the INA3221.

usage: python3 ina_inrush.py [hub] [port] [trials] [tag] [samples]    default 1-1 3 3 run 8000
Switches <port> off, starts a fast capture on the controller, switches the
port on 0.15 s later, and records the port's current for samples x ~250 us
(8000 = about 2 s, long enough for an ESP32 to start WiFi).
Controller: PA_CTRL=<usb path>, or hub port 4.

The INA3221 is set to the one channel, shunt-voltage only, 140 us conversion,
no averaging (config 0x4005 / 0x2005 / 0x1005), then restored to the power-on
default 0x7127. Shunt LSB 40 uV on 0.1 ohm = 0.4 mA per count, range +-1.6 A.
Each sample is the latest completed conversion, so a spike shorter than
~140 us is averaged into it, not missed or shown at full height.
Raw samples go to ../results/inrush-<tag>-p<port>-<n>.csv (t_us, ma).
"""
import os, subprocess, sys, threading
from repl import Repl, ctrl_tty

args = sys.argv[1:] + ["1-1", "3", "3", "run", "8000"][len(sys.argv) - 1:]
hub, port, trials, tag, N = args[0], int(args[1]), int(args[2]), args[3], int(args[4])
assert 1 <= port <= 3, "only ports 1-3 have an INA3221 channel"
UH = ["/usr/sbin/uhubctl", "-l", hub, "-p", str(port)]
cfg = {1: 0x4005, 2: 0x2005, 3: 0x1005}[port]
reg = 2 * port - 1  # shunt voltage register for the channel
os.makedirs("../results", exist_ok=True)

r = Repl(ctrl_tty(hub, "4"))
print("synced:", r.sync())
print(r.paste(f"""
import board, busio, time, array
for obj in ("i2c",):
    try:
        globals()[obj].deinit()
    except Exception:
        pass
try:
    board.STEMMA_I2C().deinit()
except Exception:
    pass
i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
def wr(reg, val):
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto(0x40, bytes([reg, val >> 8, val & 0xFF]))
    finally:
        i2c.unlock()
wr(0x00, {cfg})
buf = bytearray(2)
ptr = bytes([{reg}])
ts = array.array("L", [0] * {N})
vs = array.array("h", [0] * {N})
def capture():
    while not i2c.try_lock():
        pass
    try:
        t0 = time.monotonic_ns()
        for k in range({N}):
            i2c.writeto_then_readfrom(0x40, ptr, buf)
            ts[k] = (time.monotonic_ns() - t0) // 1000
            v = (buf[0] << 8) | buf[1]
            vs[k] = (v - 0x10000 if v & 0x8000 else v) >> 3
    finally:
        i2c.unlock()
    print("CAPTURED")
def dump():
    for k in range({N}):
        print(ts[k], vs[k])
print("READY")
""", wait=10))

try:
    for n in range(1, trials + 1):
        subprocess.run(UH + ["-a", "off", "-r", "30", "-w", "500"], capture_output=True)
        subprocess.run(["sleep", "3"])
        r.s.reset_input_buffer()
        r.s.write(b"capture()\r")
        t = threading.Timer(0.15, lambda: subprocess.run(UH + ["-a", "on"], capture_output=True))
        t.start()
        out = r.read_until_prompt(60)
        t.join()
        if "CAPTURED" not in out:
            print("trial", n, "capture failed:", out[-200:])
            continue
        r.s.write(b"dump()\r")
        raw = r.read_until_prompt(120)
        rows = []
        for line in raw.splitlines():
            p = line.split()
            if len(p) == 2 and p[0].isdigit() and p[1].lstrip("-").isdigit():
                rows.append((int(p[0]), int(p[1]) * 0.4))
        if not rows:
            print("trial", n, "no samples parsed:", raw[-200:])
            continue
        fn = f"../results/inrush-{tag}-p{port}-{n}.csv"
        with open(fn, "w") as f:
            f.write("t_us,ma\n")
            f.writelines(f"{t},{ma:.1f}\n" for t, ma in rows)
        on = next((t for t, ma in rows if ma > 5), None)
        peak_t, peak = max(rows, key=lambda x: x[1])
        span = rows[-1][0] - rows[0][0]
        def window(a_ms, b_ms):
            xs = [ma for t, ma in rows if on is not None and on + a_ms * 1000 <= t < on + b_ms * 1000]
            return max(xs) if xs else None
        tail = [ma for t, ma in rows[-200:]]
        print(f"trial {n}: {len(rows)} samples over {span/1000:.0f} ms ({span/len(rows):.0f} us/sample) | "
              f"current starts {None if on is None else round(on/1000, 1)} ms | peak {peak:.1f} mA at "
              f"{None if on is None else round((peak_t - on)/1000, 1)} ms after start | "
              f"max 0-10 ms {window(0, 10)} | 10-200 ms {window(10, 200)} | 200 ms+ {window(200, 1e9)} | "
              f"last 50 ms avg {sum(tail)/len(tail):.1f} mA -> {fn}", flush=True)
finally:
    print(r.paste("wr(0x00, 0x7127); i2c.deinit(); print('INA3221 config restored')", wait=5))
    r.close()
