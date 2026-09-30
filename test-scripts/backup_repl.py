"""Back up every file on a CircuitPython board over the serial REPL (base64).

usage: python3 backup_repl.py <hub_path> <port> <out_dir> [bridge]
For boards with no CIRCUITPY drive (ESP32 over a USB-UART bridge). Pass
'bridge' as the 4th argument for CH9102/CP210x boards. Prints path, size and
md5 of each file written, plus the board-side size for comparison.
"""
import base64, hashlib, os, sys, time
from repl import Repl, by_path

hub, port, out = sys.argv[1], sys.argv[2], sys.argv[3]
bridge = len(sys.argv) > 4 and sys.argv[4] == "bridge"
r = Repl(by_path(hub, port), bridge=bridge)
if bridge:
    time.sleep(6)  # opening may reboot an ESP32; let it finish before Ctrl-C
print("synced:", r.sync())
out_txt = r.paste("""
import os, binascii
def walk(p):
    for n in os.listdir(p):
        f = p.rstrip("/") + "/" + n
        st = os.stat(f)
        if st[0] & 0x4000:
            walk(f)
        else:
            with open(f, "rb") as fh:
                data = fh.read()
            print("B64", f, st[6], binascii.b2a_base64(data).decode().strip())
walk("/")
print("B64DONE")
""", wait=180)
r.close(False)
n = 0
for line in out_txt.splitlines():
    if not line.startswith("B64 "):
        continue
    parts = line.split(" ", 3)
    path, size = parts[1], int(parts[2])
    data = base64.b64decode(parts[3]) if len(parts) > 3 else b""
    dest = os.path.join(out, path.lstrip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    ok = "ok" if len(data) == size else f"SIZE MISMATCH board {size}"
    print(f"{hashlib.md5(data).hexdigest()}  {len(data):>6}  {path}  {ok}")
    n += 1
print(f"{n} files, done marker {'seen' if 'B64DONE' in out_txt else 'MISSING'}")
