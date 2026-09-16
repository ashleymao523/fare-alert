# -*- coding: utf-8 -*-
"""v1.05 acceptance: bookmarklet v2 card capture + lowest-wins cache
+ in-place DayDetail point-fill form."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.point_fill import (build_bookmarklet, gap_dates,
                             patch_snapshot_deals, put_rows)

RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(("PASS" if cond else "FAIL"), name, extra)


def main():
    tmp = tempfile.mkdtemp(prefix="fa_v105_")
    try:
        rows = [
            {"date": "2026-10-15", "total": 520, "flight_no": "GJ5401",
             "dep_time": "07:45", "arr_time": "10:30"},
            {"date": "2026-10-15", "total": 480, "flight_no": "PN6436",
             "dep_time": "16:55", "arr_time": "19:40"},
            {"date": "2026-10-16", "total": 610, "flight_no": "SC2114",
             "dep_time": "08:00", "arr_time": "12:20"},
        ]
        cache, n = put_rows(tmp, "hangzhou-chongqing", rows, tax=120.0, now=1000.0)
        check("put_rows stores one entry per date", n == 2, "n=%s" % n)
        e = cache["hangzhou-chongqing"]["2026-10-15"]
        check("lowest total wins the date slot",
              abs(e["total"] - 480.0) < 0.01 and e["flight_no"] == "PN6436",
              "total=%s fno=%s" % (e.get("total"), e.get("flight_no")))
        check("bare keeps total-tax semantics",
              abs(e["bare"] - 360.0) < 0.01, "bare=%s" % e.get("bare"))
        deals = [{"date": "2026-10-15", "source": "booking-ref",
                  "bare_price": 700.0, "total_price": 820.0},
                 {"date": "2026-10-16", "source": "qunar-calendar",
                  "bare_price": 300.0, "total_price": 420.0}]
        patched = patch_snapshot_deals(deals, cache, "hangzhou-chongqing",
                                       now=1000.0)
        check("booking-ref row patched to captured price", patched == 1,
              "patched=%s" % patched)
        check("real qunar row untouched",
              deals[1]["total_price"] == 420.0
              and deals[1]["source"] == "qunar-calendar")
        check("patched row carries exact times",
              deals[0]["dep_time"] == "16:55"
              and deals[0]["time_src"] == "point-fill")
        gaps = gap_dates(deals, ["2026-10-15", "2026-10-17"])
        check("point-filled date leaves the gap list; tail gap stays",
              gaps == ["2026-10-17"],
              "gaps=%s" % gaps)
        bm = build_bookmarklet("http://192.168.1.8:8765/")
        check("bookmarklet binds origin", "http://192.168.1.8:8765" in bm)
        check("bookmarklet v2 card capture present",
              "cardOf" in bm and "cards" in bm and "slice(0,12)" in bm)
        body = bm[len("javascript:"):]
        jsp = os.path.join(tmp, "bm.js")
        with open(jsp, "w", encoding="utf-8") as f:
            f.write(body)
        try:
            p = subprocess.run(["node", "--check", jsp], capture_output=True,
                               timeout=15)
            check("bookmarklet JS parses (node --check)", p.returncode == 0,
                  (p.stderr or b"").decode("utf-8", "ignore")[:120])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("SKIP bookmarklet JS parse (node unavailable)")
        root = os.path.join(os.path.dirname(__file__), "..")
        dd = open(os.path.join(root, "web", "src", "components",
                               "DayDetail.jsx"), encoding="utf-8").read()
        check("DayDetail imports postPointFill",
              "postPointFill" in dd.splitlines()[2])
        check("DayDetail in-place form rendered for reference days",
              "pf-inline" in dd and "isRefPrice" in dd)
        cv = open(os.path.join(root, "web", "src", "components",
                               "CrawlView.jsx"), encoding="utf-8").read()
        check("CrawlView bookmarklet copy says v2 full-list capture",
              "v2" in cv and "全部航班" in cv)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [r for r in RESULTS if not r[1]]
    print("----")
    print("v1.05 checks: %d pass / %d fail" % (len(RESULTS) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
