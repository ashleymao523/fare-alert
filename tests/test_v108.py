# -*- coding: utf-8 -*-
"""v1.08 acceptance: balance 2.0 - severe-dow multi-date probing,
full-day offer limit passthrough, severe/normal TTL split."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.dow_balance import (dow_coverage, weak_dows, _next_dates,
                              balance_once, SEVERE_RATIO)

RESULTS = []


def check(name, cond, extra=""):
    RESULTS.append((name, bool(cond), extra))
    print(("PASS" if cond else "FAIL"), name, extra)


def _db(dows_n):
    fl = {}
    for dow, n in dows_n.items():
        for i in range(n):
            fl["XX%04d" % (dow * 1000 + i)] = {
                "dows": {str(dow): {"dep": "08:00", "arr": "10:00"}}}
    return {"updated": 0, "flights": fl}


class _Fetch(object):
    def __init__(self, offers=None, fail=False):
        self.calls = []       # (fi, ti, date, offer_limit)
        self.offers = offers or []
        self.fail = fail

    def __call__(self, session, net_cfg, fi, ti, date, offer_limit=8):
        self.calls.append((fi, ti, date, offer_limit))
        if self.fail:
            raise RuntimeError("boom")
        return {"total_eur": 100.0, "no_data": False,
                "offers": self.offers}


def main():
    today = dt.date.today()          # balance_once uses date.today()
    # 1. severe vs weak-only db: dow5 27% (weak), dow6 1% (severe)
    db = _db({0: 100, 1: 100, 2: 100, 3: 100, 4: 100, 5: 27, 6: 1})
    cov = dow_coverage(db)
    peak = max(cov.values())
    check("dow6 is severe (<20% peak)",
          cov["6"] < peak * SEVERE_RATIO
          and cov["5"] >= peak * SEVERE_RATIO)
    sat3 = _next_dates(5, 3, today=today)
    sun3 = _next_dates(6, 3, today=today)
    check("3 Sat dates in window",
          len(sat3) == 3 and all(d for d in sat3), str(sat3))
    check("3 Sun dates in window",
          len(sun3) == 3 and all(d for d in sun3), str(sun3))

    # 2. round with severe dow6 + weak dow5: dow6 probes 3 dates x
    #    1 route, dow5 probes 1 date; offer_limit=30 passthrough
    tmp = tempfile.mkdtemp()
    try:
        cfg = {"routes": [{"from_city": "杭州", "to_city": "重庆",
                           "from_iata": "HGH", "to_iata": "CKG"}]}
        offers = [{"no": "G5%04d" % i, "dep": "07:%02d" % i,
                   "arr": "09:%02d" % i} for i in range(12)]
        fx = _Fetch(offers)
        t0 = time.time()
        st = balance_once(object(), {}, cfg, db, tmp, log=None,
                          fetch=fx, now=t0)
        sat_calls = [c for c in fx.calls if c[2] in sat3]
        sun_calls = [c for c in fx.calls if c[2] in sun3]
        other = [c for c in fx.calls if c[2] not in sat3 + sun3]
        check("severe dow6 probes 3 dates", len(sun_calls) == 3,
              str([c[2] for c in sun_calls]))
        check("weak dow5 probes 1 date only",
              len(sat_calls) == 1 and len(other) == 0,
              str([c[2] for c in fx.calls]))
        check("offer_limit=30 passed through",
              all(c[3] == 30 for c in fx.calls))
        check("12 rows queued per probe x4",
              st["queued"] == 4 * 12, str(st))
        out = json.load(open(os.path.join(
            tmp, "flight_sched_db.json"), encoding="utf-8"))
        g5_3 = out["flights"].get("G50003")
        check("full-day offer sediment lands (G50003 present)",
              g5_3 is not None, str(g5_3))

        # 3. TTL split: severe present -> 4h gate; +5h runs again.
        #    dow6 (severe) resumes its 4th Sun (10-11); dow5 (weak
        #    but not severe) takes its NEXT single date (09-26)
        fx2 = _Fetch(offers)
        st2 = balance_once(object(), {}, cfg, out, tmp, log=None,
                           fetch=fx2, now=t0 + 5 * 3600)
        new_dates = sorted({c[2] for c in fx2.calls})
        check("severe 4h TTL: +5h round runs new dates",
              st2["probed"] > 0
              and set(new_dates) == {sat3[1], _next_dates(6, 4, today=today)[3]},
              str(new_dates))

        # 4. no-severe db: 12h gate holds at +5h
        db_weak_only = _db({0: 100, 1: 100, 2: 100, 3: 100, 4: 100,
                            5: 30, 6: 30})  # both weak, NOT severe
        tmp2 = tempfile.mkdtemp()
        try:
            fx3 = _Fetch(offers)
            t1 = time.time()
            balance_once(object(), {}, cfg, db_weak_only, tmp2,
                         log=None, fetch=fx3, now=t1)
            fx4 = _Fetch(offers)
            st4 = balance_once(object(), {}, cfg, db_weak_only, tmp2,
                               log=None, fetch=fx4,
                               now=t1 + 5 * 3600)
            check("weak-only db: 12h gate blocks +5h",
                  st4["probed"] == 0 and len(fx4.calls) == 0,
                  str(st4))
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = [r for r in RESULTS if not r[1]]
    print("v1.08 checks: %d pass, %d fail" % (
        len(RESULTS) - len(bad), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
