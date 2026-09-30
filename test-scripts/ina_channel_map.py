"""T5: map INA3221 channels to hub ports by switching one port off at a time.

usage: PA_CTRL=<controller usb path> python3 ina_channel_map.py [hub_path] [ports]    default 1-1 1,2,3,4
Reads all three channels (ina3221_volts.py, 10 samples) with every port on,
then with each port off in turn. The channel whose voltage and current drop to
zero is that port's. A port with no channel changes nothing (port 4 by design).
"""
import re, subprocess, sys, time

args = sys.argv[1:] + ["1-1", "1,2,3,4"][len(sys.argv) - 1:]
hub, ports = args[0], args[1].split(",")


def read():
    out = subprocess.run([sys.executable, "ina3221_volts.py", "x-x", "0", "10"],
                         capture_output=True, text=True).stdout
    vals = {}
    for m in re.finditer(r"CH(\d) port\d bus V min [\d.]+ avg ([\d.]+) max [\d.]+ \| mA min [-\d.]+ avg ([-\d.]+)", out):
        vals[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
    return vals


def uh(p, action):
    subprocess.run(["/usr/sbin/uhubctl", "-l", hub, "-p", p, "-a", action], capture_output=True)


def show(label, v):
    cells = "  ".join(f"ch{c}: {v[c][0]:.3f} V {v[c][1]:6.1f} mA" for c in sorted(v))
    print(f"{label:<14} {cells}", flush=True)


for p in ports:
    uh(p, "on")
time.sleep(15)
base = read()
show("all on", base)
for p in ports:
    uh(p, "off")
    time.sleep(3)
    v = read()
    show(f"port {p} off", v)
    dropped = [c for c in v if base[c][0] > 1 and v[c][0] < 0.5]
    print(f"   -> port {p} = {'ch' + str(dropped[0]) if len(dropped) == 1 else ('none' if not dropped else dropped)}", flush=True)
    uh(p, "on")
    time.sleep(15)
