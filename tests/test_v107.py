# -*- coding: utf-8 -*-
"""v1.07 acceptance: dow balance - starved-dow detect, future-date
probe through fetch_lowest, deposit queue mapping, absorb under the
row's own weekday, throttle, and observed-entry safety."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.dow_balance import (dow_coverage, weak_dows, _next_date,
                              balance_once)

RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(("PASS" if cond else "FAIL"), name, extra)


def _db(dows_n):
    # dows_n: {dow: n_rows} - fill with dummy flights
    fl = {}
    for dow, n in dows_n.items():
        for i in range(n):
            fl["XX%04d" % (dow * 1000 + i)] = {
                "dows": {str(dow): {"dep": "08:00", "arr": "10:00"}}}
    return {"updated": 0, "flights": fl}


class _Fetch(object):
    def __init__(self, offers=None, fail=False):
        self.calls = []
        self.offers = offers or []
        self.fail = fail

    def __call__(self, session, net_cfg, fi, ti, date):
        self.calls.append((fi, ti, date))
        if self.fail:
            raise RuntimeError("boom")
        return {"total_eur": 100.0, "no_data": False,
                "offers": self.offers}


def main():
    today = dt.date(2026, 9, 16)     # a Wednesday (dow=2)
    # 1. coverage + starved dows: weekend hole => [5, 6]
    db = _db({0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 10, 6: 0})
    cov = dow_coverage(db)
    check("coverage counts 7 dows",
          cov == {"0": 100, "1": 100, "2": 100, "3": 100,
                  "4": 100, "5": 10, "6": 0}, str(cov))
    check("weekend-off db yields weak dows [5, 6]",
          weak_dows(db) == [5, 6], str(weak_dows(db)))
    check("empty db yields no weak dows", weak_dows({"flights": {}}) == [])
    even = _db({i: 100 for i in range(7)})
    check("even db yields no weak dows", weak_dows(even) == [])

    # 2. next probe date: +2..+25 window, right weekday
    sat = _next_date(5, today=today)
    sun = _next_date(6, today=today)
    check("next Sat is 2026-09-19", sat == "2026-09-19", sat)
    check("next Sun is 2026-09-20", sun == "2026-09-20", sun)
    d = dt.date.fromisoformat(sat)
    check("probe date weekday == 5", d.weekday() == 5)
    check("bad dow yields ''", _next_date(9, today=today) == "")

    # 3. balance round: fake fetch -> queue -> absorb under own dow
    tmp = tempfile.mkdtemp()
    try:
        cfg = {"routes": [{"from_city": "杭州", "to_city": "重庆",
                           "from_iata": "HGH", "to_iata": "CKG"}]}
        offers = [
            {"no": "3u8084", "dep": "07:15", "arr": "09:50"},  # lower
            {"no": "MF8475", "dep": "11:30", "arr": "14:05"},
            {"no": "", "dep": "12:00", "arr": "14:00"},        # dropped
        ]
        fx = _Fetch(offers)
        t0 = time.time()
        st = balance_once(object(), {}, cfg, db, tmp, log=None,
                          fetch=fx, now=t0)
        check("probed 2 weak dows x 1 route", st["probed"] == 2
              and len(fx.calls) == 2, str(st))
        check("queued 2x2 mapped rows", st["queued"] == 4, str(st))
        check("absorbed into board db", st["absorbed"] == 4, str(st))
        check("probe dates are Sat+Sun",
              [c[2] for c in fx.calls] == ["2026-09-19", "2026-09-20"],
              str(fx.calls))
        out = json.load(open(os.path.join(
            tmp, "flight_sched_db.json"), encoding="utf-8"))
        f3u = out["flights"].get("3U8084")
        check("3U8084 filed under Sat (dow 5)",
              f3u is not None and "5" in f3u["dows"], str(f3u))
        fmf = out["flights"].get("MF8475")
        check("MF8475 filed under Sun (dow 6)",
              fmf is not None and "6" in fmf["dows"], str(fmf))
        check("flight no uppercased + dep kept",
              f3u["dows"]["5"].get("dep") == "07:15")

        # 4. observed entries win: re-run with a DIFFERENT time must
        #    not overwrite the absorbed 07:15
        fx2 = _Fetch([{"no": "3U8084", "dep": "23:59", "arr": "01:30"}])
        st2 = balance_once(object(), {}, cfg, out, tmp, log=None,
                           fetch=fx2, now=t0 + 13 * 3600)
        out2 = json.load(open(os.path.join(
            tmp, "flight_sched_db.json"), encoding="utf-8"))
        check("re-balance keeps observed dep 07:15",
              out2["flights"]["3U8084"]["dows"]["5"]["dep"] == "07:15")

        # 5. throttle: inside RUN_TTL nothing probed
        fx3 = _Fetch([{"no": "CA1855", "dep": "09:00", "arr": "11:30"}])
        st3 = balance_once(object(), {}, cfg, out2, tmp, log=None,
                           fetch=fx3, now=t0 + 100)
        check("12h throttle blocks a second round",
              st3["probed"] == 0 and len(fx3.calls) == 0, str(st3))

        # 6. fetch failure never raises, absorbs nothing
        tmp2 = tempfile.mkdtemp()
        try:
            fxf = _Fetch(fail=True)
            stf = balance_once(object(), {}, cfg, db, tmp2, log=None,
                               fetch=fxf, now=t0)
            check("failed probe: no raise, 0 queued",
                  stf["probed"] == 2 and stf["queued"] == 0, str(stf))
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = [r for r in RESULTS if not r[1]]
    print("v1.07 checks: %d pass, %d fail" % (
        len(RESULTS) - len(bad), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
