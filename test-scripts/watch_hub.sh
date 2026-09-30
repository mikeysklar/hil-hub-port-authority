#!/bin/sh
# T7: watch a hub and its ports appear/disappear for N seconds, printing each change.
# usage: sh watch_hub.sh [hub_path] [seconds]    default 1-2 60
HUB=${1:-1-2}; SECS=${2:-60}
snap() { ls -d /sys/bus/usb/devices/$HUB /sys/bus/usb/devices/$HUB.* 2>/dev/null | grep -v ':' | xargs -n1 basename 2>/dev/null | tr '\n' ' '; }
prev=""; end=$(( $(date +%s) + SECS ))
while [ "$(date +%s)" -lt $end ]; do
    cur=$(snap)
    [ "$cur" != "$prev" ] && { echo "$(date +%T.%N | cut -c1-12) present: ${cur:-<none>}"; prev=$cur; }
    sleep 0.1
done
