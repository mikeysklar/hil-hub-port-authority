"""Minimal CircuitPython REPL driver over a serial port.

Syncs on the '>>> ' prompt before sending anything: the first keystroke at
"Press any key to enter the REPL" is consumed, so unsynced commands get lost.
"""
import time
import serial


def by_path(hub_path, port):
    """Serial device for a board on hub_path (e.g. '1-2') port N, by USB path."""
    bus, chain = hub_path.split("-", 1)
    return f"/dev/serial/by-path/pci-0000:00:14.0-usb-0:{chain}.{port}:1.0"


def ctrl_tty(default_hub, default_port):
    """Serial device of the I2C controller. Set PA_CTRL to its USB path
    (e.g. '1-1' for a root port, '1-2.4' behind the hub) to override the
    hub_path/port arguments."""
    import os
    path = os.environ.get("PA_CTRL")
    if path:
        return f"/dev/serial/by-path/pci-0000:00:14.0-usb-0:{path.split('-', 1)[1]}:1.0"
    return by_path(default_hub, default_port)


class Repl:
    def __init__(self, tty, timeout=0.2, bridge=False):
        """bridge=True for USB-UART bridges (CH9102, CP2102): open without
        asserting DTR/RTS, which drive EN/IO0 auto-reset on ESP32 boards.
        Native USB CDC keeps the default, CircuitPython uses DTR as 'connected'."""
        self.bridge = bridge
        if bridge:
            self.s = serial.Serial(None, 115200, timeout=timeout, write_timeout=5)
            self.s.dtr = False
            self.s.rts = False
            self.s.port = tty
            self.s.open()
        else:
            self.s = serial.Serial(tty, 115200, timeout=timeout, write_timeout=5)

    def read_for(self, seconds):
        buf = b""
        end = time.time() + seconds
        while time.time() < end:
            buf += self.s.read(512)
        return buf.decode(errors="replace")

    def read_until_prompt(self, timeout):
        """Read until the '>>> ' prompt returns or timeout seconds pass."""
        buf = b""
        end = time.time() + timeout
        while time.time() < end and not buf.endswith(b">>> "):
            buf += self.s.read(512)
        return buf.decode(errors="replace")

    def sync(self):
        self.s.write(b"\x03\x03")
        time.sleep(0.3)
        self.s.write(b"\r")
        out = self.read_for(2)
        if ">>> " not in out:
            self.s.write(b"\r")
            out += self.read_for(2)
        return ">>> " in out

    def run(self, line, wait=1.5):
        """Send one line, return output with the echo and trailing prompt removed."""
        self.s.write(line.encode() + b"\r")
        out = self.read_for(wait)
        lines = [l for l in out.splitlines() if l.strip() not in ("", ">>>") and l.strip() != line]
        return "\n".join(lines)

    def paste(self, code, wait=3, line_delay=None):
        """Run a multi-line block via paste mode (Ctrl-E ... Ctrl-D).

        Typing blocks line by line breaks on indentation and blank lines.
        Returns the output after the block, without the paste-mode echo.
        """
        self.s.write(b"\x05")
        self.read_for(0.3)
        # one line at a time: a large single write overruns the board's input
        # UART bridges (ESP32 via CH9102) drop characters at the native-USB pace
        if line_delay is None:
            line_delay = 0.15 if self.bridge else 0.03
        for line in code.strip("\n").split("\n"):
            self.s.write(line.encode() + b"\r")
            self.read_for(line_delay)
        self.s.write(b"\x04")
        out = self.read_until_prompt(wait)
        # paste mode echoes each line with a '=== ' prefix
        return "\n".join(l for l in out.splitlines() if not l.startswith("===") and l.strip() != ">>>")

    def close(self, restart_code=True):
        if restart_code:
            self.s.write(b"\x04")  # soft reload so code.py runs again
            time.sleep(0.3)
        self.s.close()
