"""T8 debug: capture a port's VBUS power-on ramp (or the shared rail) with the INA3221.

usage: python3 ina_ramp.py [watch_ch] [switch_port] [trials] [tag]    default 1 1 5 run
  watch_ch     INA3221 channel to sample (1-3 = ports 1-3). Same as switch_port
               shows that port's own ramp; a different one shows the shared rail.
  switch_port  hub port switched off then on with uhubctl (never 4: controller).
Controller: the Adalogger on hub 1-2 port 4. Hub path fixed at 1-2.

The INA3221 is set to one channel, bus-voltage only, 140 us conversion, no
averaging (config 0x4006 / 0x2006 / 0x1006), and restored to the power-on
default 0x7127 at the end. I2C at 400 kHz. Raw samples go to
../results/ramp-<tag>-ch<watch>-p<port>-<n>.csv (t_us, volts).
"""
import os, subprocess, sys, threading, time
from repl import Repl, by_path

args = sys.argv[1:] + ["1", "1", "5", "run"][len(sys.argv) - 1:]
ch, port, trials, tag = int(args[0]), args[1], int(args[2]), args[3]
assert port != "4", "port 4 is the controller"
UH = ["/usr/sbin/uhubctl", "-l", "1-2", "-p", port]
cfg = {1: 0x4006, 2: 0x2006, 3: 0x1006}[ch]
reg = 2 * ch  # bus voltage register for the channel
N = 3000
os.makedirs("../results", exist_ok=True)

r = Repl(by_path("1-2", "4"))
print("synced:", r.sync())
print(r.paste(f"""
import board, busio, time, array
# a crashed earlier run may have left an i2c object alive in this VM
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
vs = array.array("H", [0] * {N})
def capture():
    while not i2c.try_lock():
        pass
    try:
        t0 = time.monotonic_ns()
        for k in range({N}):
            i2c.writeto_then_readfrom(0x40, ptr, buf)
            ts[k] = (time.monotonic_ns() - t0) // 1000
            vs[k] = ((buf[0] << 8) | buf[1]) >> 3
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
      time.sleep(2)
      r.s.reset_input_buffer()
      r.s.write(b"capture()\r")
      # switch on shortly after the capture starts, from a second thread
      t = threading.Timer(0.15, lambda: subprocess.run(UH + ["-a", "on"], capture_output=True))
      t.start()
      out = r.read_until_prompt(30)
      t.join()
      if "CAPTURED" not in out:
          print("trial", n, "capture failed:", out[-200:])
          continue
      r.s.write(b"dump()\r")
      raw = r.read_until_prompt(60)
      rows = []
      # a one-line for loop would wait at the '...' continuation prompt, hence dump()
      for line in raw.splitlines():
          p = line.split()
          if len(p) == 2 and p[0].isdigit() and p[1].isdigit():
              rows.append((int(p[0]), int(p[1]) * 0.008))
      if not rows:
          print("trial", n, "no samples parsed:", raw[-200:])
          continue
      fn = f"../results/ramp-{tag}-ch{ch}-p{port}-{n}.csv"
      with open(fn, "w") as f:
          f.write("t_us,volts\n")
          f.writelines(f"{t},{v:.3f}\n" for t, v in rows)
      v = [x[1] for x in rows]
      span = rows[-1][0] - rows[0][0]
      def first(th):
          for t, x in rows:
              if x >= th:
                  return t
          return None
      t_start = first(0.5)
      t45, t475 = first(4.5), first(4.75)
      after = [x for t, x in rows if t45 is not None and t >= t45]
      dip_after_45 = min(after) if after else None
      print(f"trial {n}: {len(rows)} samples over {span/1000:.1f} ms ({span/len(rows):.0f} us/sample) "
            f"first {v[0]:.3f} V  min {min(v):.3f} V  max {max(v):.3f} V  end {v[-1]:.3f} V | "
            f"0.5V@{t_start} us  4.5V@{t45} us  4.75V@{t475} us | "
            f"rise 0.5->4.5 V: {None if t_start is None or t45 is None else (t45 - t_start)} us | "
            f"min after 4.5 V: {None if dip_after_45 is None else round(dip_after_45, 3)}  -> {fn}", flush=True)

finally:
    print(r.paste("wr(0x00, 0x7127); i2c.deinit(); print('INA3221 config restored')", wait=5))
    r.close()
