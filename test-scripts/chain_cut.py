"""T11: cut the upstream port feeding a chained hub and see what its boards do.

usage: python3 chain_cut.py [parent_hub] [parent_port] [child_port] [off_s]    default 1-1 4 1 5
The child hub is <parent_hub>.<parent_port>; a CircuitPython board sits on its
<child_port>. Reads the board's uptime (time.monotonic) and reset reason
before and after switching the parent port off and on. If the board kept
running, its uptime keeps growing; if it lost power, uptime restarts near
zero and the reset reason is POWER_ON. A self-powered child hub (own 5 V)
may keep its ports powered after losing its upstream link.
"""
import os, re, subprocess, sys, time
from repl import Repl, by_path

args = sys.argv[1:] + ["1-1", "4", "1", "5"][len(sys.argv) - 1:]
parent, pport, cport, off_s = args[0], args[1], args[2], float(args[3])
child = f"{parent}.{pport}"
board = f"{child}.{cport}"
BRIDGES = ("1a86", "10c4", "0403")


def vid():
    try:
        return open(f"/sys/bus/usb/devices/{board}/idVendor").read().strip()
    except OSError:
        return None


def uptime():
    r = Repl(by_path(child, cport), bridge=vid() in BRIDGES)
    if not r.sync():
        r.close(False)
        return None
    out = r.run("import time, microcontroller as m; print('UP', time.monotonic(), m.cpu.reset_reason)")
    r.close(False)
    m = re.search(r"UP ([\d.]+) microcontroller\.ResetReason\.(\w+)", out)
    return (float(m.group(1)), m.group(2)) if m else None


def uh(*a):
    return subprocess.run(["/usr/sbin/uhubctl", "-l", parent, "-p", pport, *a],
                          capture_output=True, text=True).stdout


before = uptime()
print(f"before: board {board} uptime/reset {before}")
t_off = time.time()
uh("-a", "off", "-r", "30", "-w", "500")
time.sleep(off_s)
print(f"parent port off {off_s}s: child hub present={os.path.exists(f'/sys/bus/usb/devices/{child}')} "
      f"board present={os.path.exists(f'/sys/bus/usb/devices/{board}')}")
uh("-a", "on")
t0 = time.time()
while time.time() - t0 < 25 and not os.path.exists(by_path(child, cport)):
    time.sleep(0.1)
print(f"back: child hub + board tty after {time.time() - t0:.1f}s")
time.sleep(3)
after = uptime()
elapsed = time.time() - t_off
print(f"after:  board {board} uptime/reset {after}")
if before and after:
    kept = after[0] > before[0] + elapsed - 2
    print("RESULT:", "board kept running (ports stayed powered)" if kept
          else "board rebooted (lost power or was reset)")
