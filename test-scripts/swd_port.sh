#!/bin/sh
# T13: SWD through the hub with port power control (RP2350 + Raspberry Pi Debug Probe).
# usage: swd_port.sh [hub] [port]    default 1-1 2
# 1. port off  -> SWD attach should fail (target unpowered)
# 2. port on   -> SWD attach, reset halt, read PC, resume
# Needs the raspberrypi openocd fork (stock 0.12.0 has no rp2350.cfg).
HUB=${1:-1-1}; PORT=${2:-2}
OCD=$HOME/.local/openocd-rp2350
ocd() { timeout 20 $OCD/bin/openocd -s $OCD/share/openocd/scripts \
  -f interface/cmsis-dap.cfg -f target/rp2350.cfg -c "adapter speed 5000" "$@" 2>&1 \
  | grep -E "DPIDR|Examination|Error|halted|pc|xPSR|failed" ; }

echo "== port $PORT off"
/usr/sbin/uhubctl -l $HUB -p $PORT -a off -r 30 -w 500 | grep "Port $PORT" | tail -1
sleep 2
ocd -c "init; shutdown"
echo "== port $PORT on"
/usr/sbin/uhubctl -l $HUB -p $PORT -a on | grep "Port $PORT" | tail -1
sleep 3
ocd -c "init; reset halt; reg pc; resume; shutdown"
sleep 5
echo "== usb: $(cat /sys/bus/usb/devices/$HUB.$PORT/product 2>/dev/null || echo gone)"
