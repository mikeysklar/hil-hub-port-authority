"""Read microcontroller.cpu.reset_reason and supervisor.runtime.run_reason.

usage: python3 reset_reason.py [hub_path] [port]    default 1-2 1
POWER_ON after a uhubctl cycle means VBUS was really cut.
"""
import sys
from repl import Repl, by_path

args = sys.argv[1:] + ["1-2", "1"][len(sys.argv) - 1:]
r = Repl(by_path(args[0], args[1]))
print("synced:", r.sync())
print(r.run("import microcontroller as m, supervisor; print(m.cpu.reset_reason, supervisor.runtime.run_reason)"))
r.close()
