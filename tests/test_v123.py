# -*- coding: utf-8 -*-
"""v1.23 acceptance: on-demand per-route ctrip time backfill."""
import datetime as _dt
import json
import os
import sys
import tempfile
import unittest
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import cdp_board as cb


def _hist():
    return {"routes": {
        "pek-sha": {
            "from_city": "北京", "to_city": "上海",
            "obs": [
                {"fno": "MU5137", "date": "2026-10-20"},
                {"fno": "HO1254", "date": "2026-10-25"},
                {"fno": "HO1254", "date": "2026-10-18"},
                {"fno": "OLD1", "date": "2026-01-01"},
                {"fno": "TIMED1", "date": "2026-10-19", "dep": "08:00"},
            ],
        },
        "hgh-can": {
            "from_city": "杭州", "to_city": "广州",
            "obs": [{"fno": "CZ3333", "date": "2026-10-10"}],
        },
    }}


TODAY = _dt.date(2026, 9, 17)


class TestRouteTargets(unittest.TestCase):
    def test_city_filter_earliest_first_cap(self):
        ts = cb.route_targets(_hist(), "北京", "上海", max_fnos=8,
                              today=TODAY)
        # OLD1 (past) and TIMED1 (already timed) excluded; per-fno
        # earliest date wins: HO1254 -> 10-18.
        self.assertEqual(ts, [
            {"fno": "HO1254", "date": "2026-10-18"},
            {"fno": "MU5137", "date": "2026-10-20"},
        ])

    def test_max_fnos_truncates(self):
        ts = cb.route_targets(_hist(), "北京", "上海", max_fnos=1,
                              today=TODAY)
        self.assertEqual(ts, [{"fno": "HO1254", "date": "2026-10-18"}])

    def test_other_legs_excluded(self):
        ts = cb.route_targets(_hist(), "杭州", "广州", max_fnos=8,
                              today=TODAY)
        self.assertEqual(ts, [{"fno": "CZ3333", "date": "2026-10-10"}])

    def test_city_exact_contract(self):
        # Page sends exact stored city; superset names do NOT match
        # here (containment lives in _apply_exact, by design).
        self.assertEqual(cb.route_targets(_hist(), "北京大兴", "上海",
                                          today=TODAY), [])


class TestFillRoute(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig_fetch = cb.fetch_flight
        self.addCleanup(setattr, cb, "fetch_flight", self._orig_fetch)

    def test_neg_cache_short_circuit(self):
        for fno, date in (("HO1254", "2026-10-18"),
                          ("MU5137", "2026-10-20")):
            cb._atomic_write(
                cb._cache_path(self.tmp, fno, date),
                {"ts": time.time(), "row": None, "neg": True})

        def _boom(*a, **k):
            raise AssertionError("must not query under neg cache")

        cb.fetch_flight = _boom
        out = cb.fill_route(_hist(), self.tmp, "北京", "上海", max_fnos=8)
        self.assertEqual(out["stats"]["neg"], 2)
        self.assertEqual(out["stats"]["fnos"], 0)
        self.assertEqual(out["rows"], [])

    def test_breaker_after_two_fails(self):
        calls = []

        def _boom(net_cfg, data_dir, fno, date_iso, force=False):
            calls.append(fno)
            raise RuntimeError("stub offline")

        cb.fetch_flight = _boom
        out = cb.fill_route(_hist(), self.tmp, "北京", "上海", max_fnos=8)
        self.assertTrue(out["stats"].get("breaker"))
        self.assertEqual(len(calls), 2)
        self.assertEqual([r["how"] for r in out["rows"]],
                         ["fail", "fail"])

    def test_capped_short_circuit(self):
        cb.fetch_flight = lambda *a, **k: (None, "capped")
        out = cb.fill_route(_hist(), self.tmp, "北京", "上海", max_fnos=8)
        self.assertTrue(out["stats"]["capped"])
        self.assertEqual(out["stats"]["fnos"], 0)
        self.assertEqual(out["rows"], [])

    def test_normal_flow_updates_history_and_db(self):
        hist = _hist()

        def _fake(net_cfg, data_dir, fno, date_iso, force=False):
            if fno == "HO1254":
                return ({"fno": "HO1254", "dep": "21:25",
                         "arr": "23:40", "from": "北京大兴",
                         "to": "上海浦东", "src": "ctrip-detail"},
                        "net")
            return (None, "net")

        cb.fetch_flight = _fake
        out = cb.fill_route(hist, self.tmp, "北京", "上海", max_fnos=8)
        st = out["stats"]
        self.assertEqual(st["queries"], 2)
        self.assertEqual(st["exact"], 1)
        self.assertEqual(st["filled"], 1)
        self.assertEqual(st["fnos"], 2)
        self.assertEqual([r["fno"] for r in out["rows"]],
                         ["HO1254", "MU5137"])
        self.assertEqual(out["rows"][0]["dep"], "21:25")
        # history mutated in place: the 10-18 obs got its times.
        obs = hist["routes"]["pek-sha"]["obs"]
        hit = [o for o in obs if o["fno"] == "HO1254"
               and o["date"] == "2026-10-18"][0]
        self.assertEqual(hit["dep"], "21:25")
        self.assertEqual(hit["tsrc"], "ctrip-detail")
        # sched db persisted.
        with open(os.path.join(self.tmp, cb.DB_NAME),
                  encoding="utf-8") as f:
            db = json.load(f)
        self.assertIn("HO1254", db["flights"])


if __name__ == "__main__":
    unittest.main()
