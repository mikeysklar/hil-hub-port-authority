"""T9d: write a USB2514B config image with custom strings to the hub's 24LC02.

usage: python3 eeprom_write.py [hub] [manufacturer] [product] [serial] [--dry-run]
  default: 1-1 "Adafruit Industries" "Port Authority" "PA-A"
Controller: PA_CTRL=<usb path>, or hub port 4 (it must stay powered, so not
on the hub being programmed when that hub is held in reset).

Before running: DIP 1 2 3 on, 4 off, and SW1 slid OFF to hold the hub in
reset, so the hub leaves the EEPROM bus alone. After: DIP 4 on (1 1 1 1) and
SW1 ON; the hub then loads this image. DIP 0 0 0 0 ignores the EEPROM again.

Image = datasheet DS00001692C section 5.1 default ROM values for the
USB2514B (VID 0424, PID 2514, self-powered, multi-TT, port swap 0x00), plus
STRING_EN (reg 0x08 bit 0), language 0x0409, and UTF-16LE strings of at
most 31 characters. Writes in 8-byte pages with ACK polling, then reads all
256 bytes back and compares. The image is saved to ../results/eeprom-<serial>.bin.
"""
import os, sys
from repl import Repl, ctrl_tty

dry = "--dry-run" in sys.argv
argv = [a for a in sys.argv[1:] if a != "--dry-run"]
args = argv + ["1-1", "Adafruit Industries", "Port Authority", "PA-A"][len(argv):]
hub, mfr, prd, ser = args[:4]

img = bytearray(256)
img[0x00:0x06] = bytes([0x24, 0x04, 0x14, 0x25, 0xB3, 0x0B])  # VID, PID, DID (defaults)
img[0x06] = 0x9B  # CONFIG_BYTE_1 default: self-powered, MTT, EOP disable, per-port power/OC
img[0x07] = 0x20  # CONFIG_BYTE_2 default: OC timer 8 ms
img[0x08] = 0x03  # CONFIG_BYTE_3 default 0x02 | STRING_EN
img[0x09:0x11] = bytes([0x00, 0x00, 0x00, 0x01, 0x32, 0x01, 0x32, 0x32])  # NR, port dis, power, power-on time
img[0x11], img[0x12] = 0x04, 0x09  # language ID 0x0409 (English US), high then low
for name, s, lenreg, start in (("manufacturer", mfr, 0x13, 0x16), ("product", prd, 0x14, 0x54),
                               ("serial", ser, 0x15, 0x92)):
    assert len(s) <= 31, f"{name} string over 31 characters"
    u = s.encode("utf-16-le")
    img[lenreg] = len(s)
    img[start:start + len(u)] = u
# 0xD0 battery charging, 0xF6/0xF8 boost, 0xFA port swap, 0xFB/0xFC port map: all 0 (defaults)

os.makedirs("../results", exist_ok=True)
fn = f"../results/eeprom-{ser}.bin"
open(fn, "wb").write(img)
for base in range(0, 256, 16):
    print("IMG %02x:" % base, " ".join("%02x" % x for x in img[base:base + 16]))
print("saved", fn)
if dry:
    sys.exit(0)

r = Repl(ctrl_tty(hub, "4"))
print("synced:", r.sync())
out = r.paste(f"""
import board, time, binascii
img = binascii.a2b_base64("{__import__('base64').b64encode(img).decode()}")
try:
    i2c.deinit()
except Exception:
    pass
i2c = board.STEMMA_I2C()
while not i2c.try_lock():
    pass
try:
    print("SCAN", [hex(a) for a in i2c.scan()])
    retries = 0
    for page in range(0, 256, 8):
        # a page write can be NACKed now and then (seen once at 0x58);
        # rewriting a page is harmless, so retry it, then ACK-poll the write cycle
        for attempt in range(5):
            try:
                i2c.writeto(0x50, bytes([page]) + img[page:page + 8])
                break
            except OSError:
                retries += 1
                time.sleep(0.01)
        else:
            raise OSError("page 0x%02x not acknowledged after 5 tries" % page)
        # monotonic_ns: time.monotonic() is a float that gets too coarse after
        # days of uptime to time a 50 ms window
        t0 = time.monotonic_ns()
        while True:
            try:
                i2c.writeto(0x50, bytes([page]))
                break
            except OSError:
                if time.monotonic_ns() - t0 > 50_000_000:
                    raise
    print("RETRIES", retries)
    back = bytearray(256)
    for base in range(0, 256, 16):
        b = bytearray(16)
        i2c.writeto_then_readfrom(0x50, bytes([base]), b)
        back[base:base + 16] = b
    bad = [i for i in range(256) if back[i] != img[i]]
    print("VERIFY", "OK" if not bad else "MISMATCH at " + ",".join(hex(i) for i in bad[:16]))
finally:
    i2c.unlock()
    i2c.deinit()
""", wait=20)
print("\n".join(l for l in out.splitlines() if l.startswith(("SCAN", "VERIFY")) or "Error" in l))
r.close()
