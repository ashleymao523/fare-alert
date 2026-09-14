# -*- coding: utf-8 -*-
"""v0.45: dep-time coverage archive + daily trend series + API shape."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.history import append_history, coverage_trend, load_history


def _snap(cov=None):
    return {"routes": [{
        "id": "r1", "from_city": "杭州", "to_city": "重庆",
        "threshold_total": 600, "days_below": 1,
        "deals": [{"date": "2026-10-01", "total_price": 500,
                   "source": "qunar-calendar"}],
        **({"time_coverage": cov} if cov else {}),
    }]}


class TestCovArchive(unittest.TestCase):
    def test_metrics_carry_cov(self):
        path = os.path.join(os.path.dirname(__file__), "_cov_test.json")
        if os.path.exists(path):
            os.remove(path)
        try:
            append_history(_snap({"total": 4, "dep_exact": 3,
                                  "dep_borrow": 1, "dep_missing": 0,
                                  "arr_exact": 2, "arr_borrow": 1,
                                  "arr_est": 1, "arr_missing": 0}), path)
            days = load_history(path)["days"]
            m = list(days.values())[0]["routes"]["r1"]
            self.assertEqual(m["cov"], {"dx": 3, "db": 1, "dm": 0})
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_no_cov_block_when_absent(self):
        path = os.path.join(os.path.dirname(__file__), "_cov_test2.json")
        if os.path.exists(path):
            os.remove(path)
        try:
            append_history(_snap(), path)
            m = list(load_history(path)["days"].values())[0]["routes"]["r1"]
            self.assertNotIn("cov", m)
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestCoverageTrend(unittest.TestCase):
    def _hist(self):
        days = {}
        for day, (dx, db, dm) in {
            "2026-09-10": (1, 1, 2),   # 25%
            "2026-09-11": (2, 1, 1),   # 50%
            "2026-09-12": (3, 1, 0),   # 75%
        }.items():
            days[day] = {"routes": {
                "r1": {"cov": {"dx": dx, "db": db, "dm": dm}},
                "r2": {"cov": {"dx": dx, "db": 0, "dm": 0}},
            }}
        # pre-v0.45 day without cov must be skipped, not plotted as 0%
        days["2026-09-09"] = {"routes": {"r1": {"cheapest_total": 1}}}
        return {"days": days}

    def test_series_math_and_order(self):
        out = coverage_trend(self._hist())
        self.assertEqual([o["date"] for o in out],
                         ["2026-09-10", "2026-09-11", "2026-09-12"])
        # r1(1,1,2)+r2(1,0,0) -> de 2 / db 1 / dm 2
        self.assertEqual(out[0]["de"], 2)
        self.assertEqual(out[0]["tot"], 5)
        self.assertAlmostEqual(out[0]["pct"], 40.0)
        # 2026-09-12: r1(3,1,0)+r2(3,0,0) -> 6/7
        self.assertAlmostEqual(out[2]["pct"], 85.7)

    def test_days_cap(self):
        out = coverage_trend(self._hist(), days=2)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[-1]["date"], "2026-09-12")

    def test_empty_history(self):
        self.assertEqual(coverage_trend({"days": {}}), [])


class TestCovEndpoint(unittest.TestCase):
    def test_endpoint_shape(self):
        import webui
        c = webui.app.test_client()
        r = c.get("/api/coverage-trend")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["ok"])
        self.assertIsInstance(j["trend"], list)
        for pt in j["trend"]:
            self.assertIn("date", pt)
            self.assertIn("pct", pt)
            self.assertIn("tot", pt)


if __name__ == "__main__":
    unittest.main()
