#!/bin/sh
# T12 demo: switch hub ports off and on one at a time while the OLED shows it.
# usage: oled_demo.sh [hub] [ports] [off_s]    default 1-2 "4 2" 10
# Needs controller/oled_ports.py running as code.py on the controller and
# oled_push.py running on this host, for example:
#   PA_CTRL=1-6.3.4.1 python3 oled_push.py 1-1 4 0 &
#   ./oled_demo.sh 1-1 "1 2 3 4" 10
HUB=${1:-1-2}; PORTS=${2:-"4 2"}; OFF=${3:-10}
for p in $PORTS; do
  date +"%T port $p off"
  /usr/sbin/uhubctl -l $HUB -p $p -a off -r 30 -w 500 >/dev/null
  sleep $OFF
  date +"%T port $p on"
  /usr/sbin/uhubctl -l $HUB -p $p -a on >/dev/null
  sleep 6
done
