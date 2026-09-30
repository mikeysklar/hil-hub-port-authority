"""T12: push hub port power state to the OLED controller (controller/oled_ports.py).

usage: python3 oled_push.py [hub_path] [controller_port] [seconds]    default 1-2 4 0
Reads `uhubctl -l <hub>` every second and sends "PA 1101\n" (port 1..4
power bit, 0x0100) to the controller's USB serial. seconds=0 runs until
Ctrl-C. Set PA_CTRL=<usb path> when the controller is not on the hub.
The controller must be running oled_ports.py as code.py, not sitting at the
REPL (a REPL would echo the lines).
"""
import re, subprocess, sys, time
import serial
from repl import ctrl_tty

args = sys.argv[1:] + ["1-2", "4", "0"][len(sys.argv) - 1:]
hub, secs = args[0], float(args[2])
tty = ctrl_tty(hub, args[1])


def power_bits():
    out = subprocess.run(["/usr/sbin/uhubctl", "-l", hub], capture_output=True, text=True).stdout
    st = dict(re.findall(r"Port (\d): ([0-9a-f]{4})", out.split("Current status")[-1]))
    return "".join("1" if int(st[p], 16) & 0x0100 else "0" if p in st else "?"
                   for p in "1234")


s = serial.Serial(tty, 115200, timeout=0, write_timeout=5)
t0 = time.time()
last = None
try:
    while secs == 0 or time.time() - t0 < secs:
        bits = power_bits()
        s.write(f"PA {bits}\n".encode())
        if bits != last:
            print(time.strftime("%T"), "PA", bits, flush=True)
            last = bits
        time.sleep(1)
finally:
    s.close()
