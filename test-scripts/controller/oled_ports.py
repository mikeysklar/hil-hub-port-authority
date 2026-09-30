# Port Authority I2C controller: live port status on an SSD1306 128x64 OLED.
# T12. Deploy as code.py on the controller. OLED on hub STEMMA2 (0x3D,
# Adafruit 326 / 938), INA3221 at 0x40 on the same bus.
# Ports 1-3: bus voltage and current from the INA3221 (raw register reads,
# same math as ina3221_volts.py). Port 4 has no INA channel.
# On/off for all four ports comes from the host: oled_push.py sends
# "PA 1101\n" (port 1..4 power, from uhubctl) over USB serial. If no update
# arrives for STALE_S, on/off shows "?".
# Needs adafruit_displayio_ssd1306 and adafruit_display_text (11.x bundle).
import sys
import time
import board
import displayio
import i2cdisplaybus
import supervisor
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306

INA = 0x40
STALE_S = 5
displayio.release_displays()
i2c = board.STEMMA_I2C()
bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3D)
display = adafruit_displayio_ssd1306.SSD1306(bus, width=128, height=64)

group = displayio.Group()
group.append(label.Label(terminalio.FONT, text="Port Authority", x=0, y=4))
rows = []
for n in range(4):
    row = label.Label(terminalio.FONT, text="", x=0, y=16 + 12 * n)
    group.append(row)
    rows.append(row)
display.root_group = group

b = bytearray(2)
power = "????"
last_push = None
line = ""


def reg(n):
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto_then_readfrom(INA, bytes([n]), b)
    finally:
        i2c.unlock()
    v = b[0] << 8 | b[1]
    return v - 0x10000 if v & 0x8000 else v


def read_host():
    global line, power, last_push
    while supervisor.runtime.serial_bytes_available:
        c = sys.stdin.read(1)
        if c in "\r\n":
            if line.startswith("PA ") and len(line) == 7:
                power = line[3:]
                last_push = time.monotonic()
            line = ""
        else:
            line = line[-16:] + c


def state(p):
    if last_push is None or time.monotonic() - last_push > STALE_S:
        return "?  "
    return {"1": "on ", "0": "off"}.get(power[p], "?  ")


while True:
    read_host()
    for ch in range(3):
        try:
            volts = (reg(2 + 2 * ch) >> 3) * 0.008
            ma = (reg(1 + 2 * ch) >> 3) * 40e-6 / 0.1 * 1000
            rows[ch].text = "P%d %s %4.2fV %5.1fmA" % (ch + 1, state(ch), volts, ma)
        except OSError as e:
            rows[ch].text = "P%d %s read err %d" % (ch + 1, state(ch), e.errno)
    rows[3].text = "P4 %s   (no INA)" % state(3)
    time.sleep(0.2)
