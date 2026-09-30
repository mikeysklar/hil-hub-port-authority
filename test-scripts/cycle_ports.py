"""T2: round-robin power cycles over several hub ports, one port at a time.

usage: python3 cycle_ports.py [hub_path] [ports] [max_rounds] [off_s] [settle_s]    default 1-2 1,2,3 70 2 10
Each round cycles every still-active port once. A port stops at its first
failure; the run ends when every port has failed or max_rounds is reached.

Checks per board, chosen from what the board exposes before the run:
  repl   native USB CDC: reset_reason must be POWER_ON (CircuitPython)
  bridge USB-UART bridge (1a86 CH9102, 10c4 CP210x): same, opened without DTR/RTS
  enum   no serial port: must come back with its original VID:PID
Any board returning as 2e8a:0003 / 2e8a:000f (RP2040 / RP2350 ROM bootloader)
is a BOOTROM fail.
"""
import os, re, subprocess, sys, time
import serial
from repl import Repl, by_path

args = sys.argv[1:] + ["1-2", "1,2,3", "70", "2", "10"][len(sys.argv) - 1:]
hub, ports, rounds, off_s, settle_s = args[0], args[1].split(","), int(args[2]), float(args[3]), float(args[4])
BRIDGES = ("1a86", "10c4", "0403")
BOOTROM = ("2e8a:0003", "2e8a:000f")


def dev(p):
    return f"/sys/bus/usb/devices/{hub}.{p}"


def usb_id(p):
    try:
        return open(dev(p) + "/idVendor").read().strip() + ":" + open(dev(p) + "/idProduct").read().strip()
    except OSError:
        return "-"


def uh(p, *a):
    return subprocess.run(["/usr/sbin/uhubctl", "-l", hub, "-p", p, *a],
                          capture_output=True, text=True).stdout


def status(p):
    m = re.search(rf"Port {p}: (\w+)", uh(p).split("Current status")[-1])
    return m.group(1) if m else "?"


def reason(p, bridge):
    try:
        r = Repl(by_path(hub, p), bridge=bridge)
        if not r.sync():
            r.close(False)
            return "NO-PROMPT"
        out = r.run("import microcontroller as m; print('RR', m.cpu.reset_reason)")
        r.close()
        m = re.search(r"RR microcontroller\.ResetReason\.(\w+)", out)
        return m.group(1) if m else "PARSE?"
    except (serial.SerialException, OSError) as e:
        return "SERIAL-ERR"


boards = {}
for p in ports:
    vid = usb_id(p)
    name = open(dev(p) + "/product").read().strip() if os.path.exists(dev(p) + "/product") else "?"
    tty = os.path.exists(by_path(hub, p))
    mode = "bridge" if vid.split(":")[0] in BRIDGES else ("repl" if tty else "enum")
    boards[p] = {"vid": vid, "name": name, "mode": mode, "passes": 0, "failed": None}
    print(f"port {p}: {vid} {name} mode={mode}", flush=True)

print(f"hub {hub} off {off_s}s settle {settle_s}s, up to {rounds} rounds")
for n in range(1, rounds + 1):
    active = [p for p in ports if boards[p]["failed"] is None]
    if not active:
        break
    for p in active:
        b = boards[p]
        uh(p, "-a", "off", "-r", "30", "-w", "500")
        # poll for the device leaving: USB-UART bridges (CH9102) can take the
        # kernel longer than native USB boards to notice the disconnect
        t_off = time.time()
        gone_s = None
        while time.time() - t_off < off_s:
            if gone_s is None and not os.path.exists(dev(p)):
                gone_s = time.time() - t_off
            time.sleep(0.05)
        st, gone = status(p), gone_s is not None
        uh(p, "-a", "on")
        t0 = time.time()
        back = None
        while time.time() - t0 < 25:
            if os.path.exists(dev(p)) and usb_id(p) != "-":
                back = time.time() - t0
                break
            time.sleep(0.1)
        time.sleep(settle_s)
        vid = usb_id(p)
        if vid in BOOTROM:
            res = "BOOTROM"
        elif back is None or vid == "-":
            res = "GONE"
        elif b["mode"] == "enum":
            res = "ENUM-OK" if vid == b["vid"] else f"VID {vid}"
        else:
            res = reason(p, b["mode"] == "bridge")
        ok = st == "0000" and gone and res in ("POWER_ON", "ENUM-OK")
        if ok:
            b["passes"] += 1
        else:
            b["failed"] = (n, res, st, gone)
        f = "-" if back is None else f"{back:.1f}"
        g = "-" if gone_s is None else f"{gone_s:.2f}"
        print(f"round {n:<3} port {p}: off={st} gone_after={g}s back={f}s {vid} {res} {'PASS' if ok else 'FAIL'}", flush=True)
        time.sleep(1)

print("\nsummary")
for p in ports:
    b = boards[p]
    fl = "no failure" if b["failed"] is None else f"FAILED round {b['failed'][0]}: {b['failed'][1]}"
    print(f"port {p} {b['name']:<28} {b['mode']:<6} {b['passes']} passes, {fl}")
