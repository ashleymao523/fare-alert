# -*- coding: utf-8 -*-
# v0.77 run_all role matrix: FA_ROLE picks which children the
# all-in-one container entrypoint supervises.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from run_all import build_cmds

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


cmds_all = build_cmds("all")
check("all -> both children", sorted(cmds_all) == ["webui", "worker"])
check("worker argv has --loop", cmds_all["worker"][-2:] == ["main.py", "--loop"])
check("webui argv runs webui.py", cmds_all["webui"][-1] == "webui.py")

check("webui role -> webui only", sorted(build_cmds("webui")) == ["webui"])
check("worker role -> worker only", sorted(build_cmds("worker")) == ["worker"])
check("empty defaults to all", sorted(build_cmds("")) == ["webui", "worker"])
check("case-insensitive ALL", sorted(build_cmds("ALL")) == ["webui", "worker"])
check("whitespace tolerated", sorted(build_cmds(" all ")) == ["webui", "worker"])

try:
    build_cmds("bogus")
    check("bogus role raises", False)
except ValueError:
    check("bogus role raises", True)

if fails:
    print("test_run_all FAILED: %d" % len(fails))
    sys.exit(1)
print("test_run_all all OK")
