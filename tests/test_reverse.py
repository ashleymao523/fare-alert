# -*- coding: utf-8 -*-
"""M3 gate: reverse destination search unit tests. Run: python tests/test_reverse.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.models import FlightDeal
from core.reverse import (HARD_MAX_REQUESTS, candidate_pool,
                          reverse_search)

TAX = {"airport_fee": 50, "fuel_surcharge": 70}  # total = bare + 120


class _FakeFetch:
    """Returns canned deals per city; counts calls."""

    def __init__(self, table, fail_cities=()):
        self.table = table
        self.fail = set(fail_cities)
        self.calls = []

    def __call__(self, session, net, fc, tc, d1, d2):
        self.calls.append(tc)
        if tc in self.fail:
            raise RuntimeError("connection reset")
        return [FlightDeal(date=d, bare_price=p, flight_no="MU5001",
                           url="https://example.com")
                for d, p in self.table.get(tc, [])]


def _run(ff, budget=500, pool=None, max_requests=None, data_dir=None, **kw):
    d = data_dir or tempfile.mkdtemp()
    return reverse_search(None, {}, TAX, "杭州", budget,
                          "2026-10-01", "2026-11-30",
                          pool=pool or ["重庆", "成都", "西安"],
                          max_requests=max_requests, data_dir=d,
                          sleep_s=0, fetch=ff, **kw), d


def test_budget_filter_tax_included():
    ff = _FakeFetch({"重庆": [("2026-10-05", 380)],   # total 500 <= 500 hit
                     "成都": [("2026-10-06", 381)],   # total 501 > 500 no
                     "西安": []})                     # no data
    r, _ = _run(ff, budget=500)
    cities = [h["city"] for h in r["hits"]]
    assert cities == ["重庆"]                      # tax-inclusive comparison
    assert r["hits"][0]["total_price"] == 500
    assert r["scanned"] == 3 and r["failed"] == 0


def test_hard_request_budget():
    pool = ["城%02d" % i for i in range(20)]
    ff = _FakeFetch({c: [("2026-10-05", 100)] for c in pool})
    r, _ = _run(ff, budget=999, pool=pool, max_requests=5)
    assert len(ff.calls) == 5                       # budget respected exactly
    assert r["requests_used"] == 5 and r["pool_size"] == 20
    r2, _ = _run(ff, budget=999, pool=pool, max_requests=99)
    assert r2["requests_used"] <= HARD_MAX_REQUESTS  # hard cap 15


def test_cache_hit_costs_no_request():
    ff = _FakeFetch({"重庆": [("2026-10-05", 380)]})
    r1, d = _run(ff, budget=500, now_ts=1000.0)
    n1 = len(ff.calls)
    r2, _ = _run(ff, budget=500, data_dir=d, now_ts=1000.0 + 3600)  # 1h later
    assert len(ff.calls) == n1                      # all from cache
    assert r2["requests_used"] == 0
    assert r2["hits"] and r2["hits"][0]["cached"] is True


def test_failure_counted_not_fatal():
    ff = _FakeFetch({"重庆": [("2026-10-05", 100)]}, fail_cities={"成都"})
    r, _ = _run(ff, budget=999)
    assert r["failed"] == 1
    assert [h["city"] for h in r["hits"]] == ["重庆"]


def test_candidate_pool_excludes_origin():
    pool = candidate_pool("杭州")
    assert "杭州" not in pool and len(pool) >= 30


def run_all():
    fns = sorted((k, v) for k, v in list(globals().items())
                 if k.startswith("test_") and callable(v))
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print("PASS " + name)
        except Exception as e:
            failed += 1
            print("FAIL " + name + " " + repr(e))
    print("unit tests: {} pass / {} fail".format(len(fns) - failed, failed))
    return failed


if __name__ == "__main__":
    sys.exit(1 if run_all() else 0)
