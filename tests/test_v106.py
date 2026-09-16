# -*- coding: utf-8
"""v1.06 acceptance: shared-number exact-hit guard + connecting rows
first-leg departure upgrade."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.sched_board import (apply_board_upgrade_first_leg,
                              board_lookup_x)

RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(("PASS" if cond else "FAIL"), name, extra)


class _Deal(object):
    def __init__(self, **kw):
        self.flight_no = kw.get("flight_no", "CZ3502/CZ2326")
        self.dep_time = kw.get("dep_time", "13:10")
        self.arr_time = kw.get("arr_time", "16:00")
        self.dep_src = kw.get("dep_src", "booking-x")
        self.arr_src = kw.get("arr_src", "booking-x")
        self.time_src = kw.get("time_src", "booking-x")
        self.borrow_dow = kw.get("borrow_dow", "3")
        self.borrow_votes = kw.get("borrow_votes", 2)
        self.borrow_unstable = kw.get("borrow_unstable", True)


def _db(dows):
    return {"updated": 0, "flights": {"SC2118": {"dows": dows}}}


def main():
    # v1.06 guard: the real SC2118 reuse (dow2=URC->HGH, others HGH->XMN)
    db = _db({
        "2": {"dep": "11:20", "arr": "16:10",
              "from": "乌鲁木齐", "to": "杭州"},
        "3": {"dep": "17:20", "arr": "18:55",
              "from": "杭州", "to": "厦门"},
    })
    hit = board_lookup_x(db, "SC2118", "2026-10-07", "杭州", "")
    check("shared-number exact dow is downgraded (from side mismatch)",
          hit and hit[1] is False, "exact=%s" % (hit and hit[1]))
    check("cross-dow borrow keeps the leg-side flight",
          hit and hit[0]["dep"] == "17:20"
          and hit[0].get("from") == "杭州",
          "dep=%s" % (hit and hit[0].get("dep")))
    hit2 = board_lookup_x(db, "SC2118", "2026-10-08", "杭州", "")
    check("own-dow exact hit unchanged",
          hit2 and hit2[1] is True and hit2[0]["dep"] == "17:20")
    hit3 = board_lookup_x(db, "SC2118", "2026-10-07", "", "")
    check("no from filter keeps old exact behavior",
          hit3 and hit3[1] is True and hit3[0]["dep"] == "11:20")

    ent = {"dep": "18:35", "arr": "20:50", "to": "广州"}
    d = _Deal()
    ok = apply_board_upgrade_first_leg(d, ent)
    check("connecting booking-x row upgrades first-leg dep",
          ok and d.dep_time == "18:35" and d.dep_src == "airport-board",
          "dep=%s src=%s" % (d.dep_time, d.dep_src))
    check("time_src keeps weaker verdict while arr borrowed",
          d.time_src == "booking-x" and d.arr_src == "booking-x")
    check("borrow provenance cleared",
          d.borrow_dow == "" and d.borrow_votes == 0
          and d.borrow_unstable is False)

    d2 = _Deal(flight_no="PN6436")
    check("single-number rows refuse the first-leg upgrade",
          apply_board_upgrade_first_leg(d2, ent) is False
          and d2.dep_time == "13:10")
    d3 = _Deal(dep_src="amadeus", time_src="amadeus")
    check("non booking-x rows refuse the upgrade",
          apply_board_upgrade_first_leg(d3, ent) is False)
    d4 = _Deal()
    check("entry without dep refuses the upgrade",
          apply_board_upgrade_first_leg(d4, {"dep": "", "arr": "20:50"})
          is False)
    d5 = _Deal(arr_src="airport-board")
    apply_board_upgrade_first_leg(d5, ent)
    check("both sides exact lifts time_src", d5.time_src == "airport-board",
          "time_src=%s" % d5.time_src)

    root = os.path.join(os.path.dirname(__file__), "..")
    msrc = open(os.path.join(root, "main.py"), encoding="utf-8").read()
    check("main.py wires the first-leg upgrade into the / branch",
          "apply_board_upgrade_first_leg(d, ent)" in msrc)
    bf = open(os.path.join(root, "core", "booking_fill.py"),
              encoding="utf-8").read()
    check("booking_fill EXACT_SOURCES blocks re-pinning",
          '"airport-board"' in bf)
    dd = open(os.path.join(root, "web", "src", "components",
                           "DayDetail.jsx"), encoding="utf-8").read()
    check("DayDetail renders per-side dep/arr badges",
          'timeSrcBadge("起飞"' in dd and 'timeSrcBadge("落地"' in dd)

    bad = [r for r in RESULTS if not r[1]]
    print("----")
    print("v1.06 checks: %d pass / %d fail" % (len(RESULTS) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
