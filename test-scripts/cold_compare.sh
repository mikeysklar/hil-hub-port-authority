#!/bin/sh
# T4 debug: cold-boot the I2C controller with a uhubctl power cycle, then run
# i2c_compare.py. Repeats N times.
# usage: sh cold_compare.sh [hub_path] [controller_port] [count] [reads]   default 1-2 4 10 3
HUB=${1:-1-2}; PORT=${2:-4}; N=${3:-10}; READS=${4:-3}
TTY=/dev/serial/by-path/pci-0000:00:14.0-usb-0:${HUB#*-}.${PORT}:1.0
for i in $(seq 1 "$N"); do
    /usr/sbin/uhubctl -l "$HUB" -p "$PORT" -a off -r 30 -w 500 >/dev/null
    sleep 2
    /usr/sbin/uhubctl -l "$HUB" -p "$PORT" -a on >/dev/null
    t=0; while [ ! -e "$TTY" ] && [ $t -lt 250 ]; do sleep 0.1; t=$((t+1)); done
    sleep 10
    echo "== cycle $i"
    python3 "$(dirname "$0")/reset_reason.py" "$HUB" "$PORT" | grep -v synced
    python3 "$(dirname "$0")/i2c_compare.py" "$HUB" "$PORT" "$READS" | grep CASE
done
