# -*- coding: utf-8 -*-
# v0.76: doctor 纯函数单测 - PASS/WARN/FAIL 三级分级矩阵.
# Run: python -X utf8 tests/test_doctor.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.doctor import (FAIL, PASS, WARN, check_backup, check_board,
                          check_code_sync, check_deploy, check_interval,
                          check_autostart, check_push, check_snapshot,
                          check_webui, check_worker)

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def h_age(m):
    return {"snapshot": {"age_min": m}}


# webui reachability
check("webui down = FAIL", check_webui(None)[0] == FAIL)
check("webui up = PASS", check_webui({"snapshot": {}})[0] == PASS)
# snapshot freshness 三档
check("snap 30min = PASS", check_snapshot(h_age(30))[0] == PASS)
check("snap 8h = WARN", check_snapshot(h_age(8 * 60))[0] == WARN)
check("snap 30h = FAIL", check_snapshot(h_age(30 * 60))[0] == FAIL)
check("snap missing = FAIL", check_snapshot({})[0] == FAIL)
# worker heartbeat
check("worker none = WARN", check_worker({})[0] == WARN)
check("worker ok = PASS", check_worker({"worker": {"ok": True, "age_min": 10}})[0] == PASS)
check("worker last-fail = FAIL", check_worker({"worker": {"ok": False, "age_min": 10}})[0] == FAIL)
check("worker stale = FAIL", check_worker({"worker": {"ok": True, "age_min": 200}})[0] == FAIL)
# code sync
check("sync none = WARN", check_code_sync({})[0] == WARN)
check("sync ok = PASS", check_code_sync({"worker": {"code_synced": True, "code_ver": "0.76"}})[0] == PASS)
check("sync stale = FAIL", check_code_sync({"worker": {"code_synced": False}})[0] == FAIL)
# board coverage
check("board empty = WARN", check_board({})[0] == WARN)
check("board 6dows = PASS",
     check_board({"board": {"flights": 40,
                   "dows": {str(i): 5 for i in range(6)}}})[0] == PASS)
check("board 3dows = WARN",
     check_board({"board": {"flights": 40,
                   "dows": {"1": 5, "2": 5, "3": 5}}})[0] == WARN)
# backup
check("backup unknown = WARN", check_backup({})[0] == WARN)
check("backup 0 = WARN", check_backup({"backup": {"count": 0}})[0] == WARN)
check("backup 2 = PASS", check_backup({"backup": {"count": 2, "last": "x"}})[0] == PASS)
# push channel
check("push bark = PASS", check_push({"push": {"bark_key": "k"}})[0] == PASS)
check("push none = WARN", check_push({})[0] == WARN)
# poll interval red line
check("interval 45 = PASS", check_interval({"schedule": {"interval_minutes": 45}})[0] == PASS)
check("interval 10 = FAIL", check_interval({"schedule": {"interval_minutes": 10}})[0] == FAIL)
check("interval unset = WARN", check_interval({})[0] == WARN)
# v0.77 deploy form (container vs host)
_dep_lvl, _dep_msg = check_deploy()
check("deploy is PASS/WARN", _dep_lvl in (PASS, WARN))
check("deploy msg mentions form", ("容器" in _dep_msg) or ("本机" in _dep_msg))
_as_lvl, _as_msg = check_autostart()
check("autostart is PASS/WARN", _as_lvl in (PASS, WARN))
check("autostart msg actionable", ("自启" in _as_msg) or ("Windows" in _as_msg))

if fails:
    print("test_doctor FAILED: %d" % len(fails))
    sys.exit(1)
print("test_doctor all OK")
