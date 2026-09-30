"""T2: power cycle one hub port N times with uhubctl and verify each cycle.

usage: python3 cycle_port.py [hub_path] [port] [count] [off_s] [stop]    default 1-2 1 10 2
  stop: "stop" ends the run at the first BOOTROM boot
Per cycle: port reads 0000 off, device leaves the bus, returns, and the REPL
reports reset_reason POWER_ON. SAMD boards always report UNKNOWN, so for them
UNKNOWN with run_reason STARTUP passes. Target must be a CircuitPython board. A cycle that comes back as 2e8a:0003
or 2e8a:000f (RP2040 / RP2350 ROM bootloader) is reported as BOOTROM and counts as a fail.
"""
import os, re, subprocess, sys, time
import serial
from repl import Repl, by_path

args = sys.argv[1:] + ["1-2", "1", "10", "2", ""][len(sys.argv) - 1:]
stop_on_bootrom = args[4] == "stop"
hub, port, count, off_s = args[0], args[1], int(args[2]), float(args[3])
UH = ["/usr/sbin/uhubctl", "-l", hub, "-p", port]
TTY = by_path(hub, port)
DEV = f"/sys/bus/usb/devices/{hub}.{port}"


def status():
    out = subprocess.run(UH, capture_output=True, text=True).stdout
    m = re.search(rf"Port {port}: (\w+)", out.split("Current status")[-1])
    return m.group(1) if m else "?"


def usb_id():
    try:
        return open(DEV + "/idVendor").read().strip() + ":" + open(DEV + "/idProduct").read().strip()
    except OSError:
        return "-"


def devnum():
    try:
        return open(DEV + "/devnum").read().strip()
    except OSError:
        return "-"


def reason():
    try:
        return _reason()
    except (serial.SerialException, OSError) as e:
        # board or whole hub dropped off the bus mid-read; record it, keep going
        return "SERIAL-ERR", type(e).__name__


def _reason():
    r = Repl(TTY)
    if not r.sync():
        r.close(False)
        return "NO-PROMPT", "-"
    out = r.run("import microcontroller as m, supervisor; print('RR', m.cpu.reset_reason, supervisor.runtime.run_reason)")
    r.close()
    m = re.search(r"RR microcontroller\.ResetReason\.(\w+) supervisor\.RunReason\.(\w+)", out)
    return m.groups() if m else ("PARSE?", out[-60:])


print(f"hub {hub} port {port} off {off_s}s: start devnum={devnum()} status={status()}")
print("n  off   gone  bus_s tty_s devnum vid:pid   reset      run")
passed = 0
fails = {"BOOTROM": 0, "NO-TTY": 0, "SERIAL-ERR": 0, "other": 0}
for n in range(1, count + 1):
    subprocess.run(UH + ["-a", "off", "-r", "30", "-w", "500"], capture_output=True)
    time.sleep(off_s)
    st, gone = status(), not os.path.exists(DEV)
    hub_seen = os.path.exists(f"/sys/bus/usb/devices/{hub}")
    subprocess.run(UH + ["-a", "on"], capture_output=True)
    t0 = time.time()
    bus = tty = None
    while time.time() - t0 < 25 and tty is None:
        if bus is None and os.path.exists(DEV):
            bus = time.time() - t0
        if os.path.exists(TTY):
            tty = time.time() - t0
        time.sleep(0.1)
    time.sleep(10)
    vidpid = usb_id()
    if not hub_seen or not os.path.exists(f"/sys/bus/usb/devices/{hub}"):
        print(f"   note: hub {hub} itself was missing during cycle {n}", flush=True)
    # 2e8a:0003 / 2e8a:000f = RP2040 / RP2350 ROM bootloader: booted to BOOTSEL, not CircuitPython
    rr, run = reason() if tty else ("BOOTROM" if vidpid in ("2e8a:0003", "2e8a:000f") else "NO-TTY", "-")
    # atmel-samd never implements reset_reason (always UNKNOWN), so there a
    # hard boot (run_reason STARTUP) plus the observed power cut is the check
    booted = rr == "POWER_ON" or (rr == "UNKNOWN" and run == "STARTUP")
    ok = st == "0000" and gone and bus is not None and booted
    passed += ok
    if not ok:
        fails[rr if rr in fails else "other"] += 1
    f = lambda v: "-" if v is None else f"{v:.1f}"
    print(f"{n:<2} {st:<5} {str(gone):<5} {f(bus):<5} {f(tty):<5} {devnum():<6} {vidpid:<9} {rr:<10} {run}  {'PASS' if ok else 'FAIL'}", flush=True)
    if stop_on_bootrom and rr == "BOOTROM":
        count = n
        break
    time.sleep(2)
print(f"{passed}/{count} pass")
print("fails by kind:", {k: v for k, v in fails.items() if v})
