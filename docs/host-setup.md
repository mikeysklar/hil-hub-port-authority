# Port Authority hub on bene: setup notes

First JLC test run (10 boards). One hub plugged into bene.local, 2026-09-24.

## Host

- bene: Ubuntu 26.04.1 LTS, kernel 7.0.0-31-generic, x86_64
- user `sklarm` already in `plugdev` and `dialout`

## What the hub enumerates as

- Microchip USB2514, `0424:2514`, USB 2.0, 4 ports, `ppps` (per-port power switching)
- USB path `1-2` (bene root hub port 2)
- Test board: Feather RP2040 Adalogger `239a:815e`, serial `DF6380824F7A1430`, on port 1
- Serial by path: `/dev/serial/by-path/pci-0000:00:14.0-usb-0:2.1:1.0`

## Setup done

1. Installed uhubctl from apt (bravo has 2.5.0-1; bene got 2.6.0-3):

   ```sh
   sudo apt-get install -y uhubctl
   ```

2. udev rule so uhubctl runs unprivileged. Same as bravo's, plus the Microchip
   vendor ID for the new hub. `/etc/udev/rules.d/52-uhubctl.rules`:

   ```
   SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", MODE="0664", GROUP="plugdev"
   SUBSYSTEM=="usb", ATTR{idVendor}=="0424", MODE="0664", GROUP="plugdev"
   ```

   ```sh
   sudo udevadm control --reload && sudo udevadm trigger --attr-match=subsystem=usb
   ```

   Check: `ls -l /dev/bus/usb/001/<hub devnum>` shows `root plugdev crw-rw-r--`.

3. openocd for SWD through the hub (2026-09-29). The Raspberry Pi Debug
   Probe (`2e8a:000c`) is already `root:plugdev` via
   `/etc/udev/rules.d/60-picotool.rules` (all `2e8a` devices, added
   2026-09-25), so no sudo at run time. The package's own `60-openocd.rules`
   does not list `2e8a`. Stock package:

   ```sh
   sudo apt-get install -y openocd
   ```

   Stock 0.12.0 has `rp2040.cfg` but **no `rp2350.cfg`**. For the RP2350 the
   raspberrypi fork is needed. bravo's build (`0.12.0+dev-g098b86f`, built on
   Ubuntu 24.04) runs unchanged on bene, so it was copied rather than rebuilt:

   ```sh
   ssh bravo.local 'tar -C ~/.local -czf - openocd-rp2350' | tar -C ~/.local -xzf -
   ```

   Use it with its own scripts directory:

   ```sh
   OCD=~/.local/openocd-rp2350
   $OCD/bin/openocd -s $OCD/share/openocd/scripts \
     -f interface/cmsis-dap.cfg -f target/rp2350.cfg -c "adapter speed 5000"
   ```

   Check: `SWD DPIDR 0x4c013477` and both `rp2350.cm0` / `cm1` examined.

## Workarounds and gotchas

- **sudo needs a password on bene.** Installs are an attended step; `sudo -n`
  fails with "interactive authentication is required".
- **The first `! ssh -t bene.local '...'` one-liner install did nothing.** No
  package, no rule file, nothing in apt history. Running the commands directly
  in a shell on bene worked.
- **`/usr/sbin` is not on PATH for non-interactive ssh**, so
  `ssh bene.local uhubctl` gives "command not found". Use
  `export PATH=$PATH:/usr/sbin` or call `/usr/sbin/uhubctl`.
- **The installed rule file has the `0424` line split in two** (paste wrap):

  ```
  SUBSYSTEM=="usb",
    ATTR{idVendor}=="0424", MODE="0664", GROUP="plugdev"
  ```

  It still works because udev reads the second line as its own rule, but that
  rule matches vendor `0424` on any subsystem. Rejoin it onto one line.
- **sysfs port control, fixed 2026-09-28.** Without write access to the
  port `disable` files, every switching call prints `Failed to set port status
  by writing to /sys/bus/usb/devices/1-2:1.0/1-2-port1/disable (Permission
  denied)` and falls back to libusb. Power switches, but the kernel is not told:
  devices behind USB-UART bridges (ESP32 V2's CH9102) stay listed while the
  port is off. **Do not use `-S` to silence it.** Install the rule below
  instead (taken from uhubctl's own `udev/rules.d/52-usb.rules`, kernel 6.0+).
  It also rejoins the split `0424` line above. Run in a shell on bene, not via
  `ssh -t`:

  ```sh
  sudo tee /etc/udev/rules.d/52-uhubctl.rules >/dev/null <<'EOF'
  SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", MODE="0664", GROUP="plugdev"
  SUBSYSTEM=="usb", ATTR{idVendor}=="0424", MODE="0664", GROUP="plugdev"
  SUBSYSTEM=="usb", DRIVER=="hub|usb", RUN+="/bin/sh -c \"chown -f root:dialout $sys$devpath/*port*/disable || true\"", RUN+="/bin/sh -c \"chmod -f 660 $sys$devpath/*port*/disable || true\""
  EOF
  sudo udevadm control --reload && sudo udevadm trigger --attr-match=subsystem=usb
  ```

  Check: `ls -l /sys/bus/usb/devices/1-2:1.0/1-2-port1/disable` shows
  `root dialout -rw-rw----`, and `uhubctl -l 1-2 -p 1 -a off` prints no
  permission warning. User must be in `dialout`.

- **Mounting a board's drive over SSH.** `udisksctl mount` is refused
  (`NotAuthorizedCanObtain`, the ssh session has no seat). Going through the
  logged-in desktop session's gvfs works without sudo:

  ```sh
  export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
  gio mount -d /dev/sdX1        # CIRCUITPY or RPI-RP2
  gio mount -u /run/media/sklarm/CIRCUITPY
  ```

  Needs the desktop login on seat0 to exist. Right after a bootloader or
  re-enumeration, retry for a second or two: the volume is not known to gvfs
  immediately (`No volume for given ID`).

## Verified

- `uhubctl -l 1-2` unprivileged: hub listed with `ppps`, Adalogger on port 1
  (`0103 power enable connect`), ports 2-4 `0100 power`.
- Port 1 off (`-a off -r 30 -w 500`): port reads `0000 off`, Adalogger gone from
  `lsusb`.
- Port 1 on: back on the bus in 3 s, new devnum (035 -> 036), all six interfaces
  (CDC, MSC, HID, 2x audio) re-bound.
- Over the REPL after the cycle:
  `microcontroller.cpu.reset_reason` = `POWER_ON`,
  `supervisor.runtime.run_reason` = `STARTUP`. Real VBUS cut, not just a data
  disconnect. Firmware 10.3.0-alpha.3-10-g292758acc8-dirty.

## Not yet tested

- Ports 2-4 with a board attached
- Repeated cycles (one cycle is not a measurement)
- `-a cycle` in one call, and the settle time before the board is usable
- Other nine boards from the run
