# -*- coding: utf-8 -*-
"""v0.55: day_drops pure compare + /api/drops contract."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.history import day_drops


def _hist():
    return {"days": {
        "2026-09-13": {"routes": {
            "a": {"from_city": "杭州", "to_city": "重庆",
                  "cheapest_total": 600.0},
            "b": {"from_city": "杭州", "to_city": "郑州",
                  "cheapest_total": 300.0},
            "c": {"from_city": "杭州", "to_city": "成都",
                  "cheapest_total": 500.0},
        }},
        "2026-09-14": {"routes": {
            "a": {"from_city": "杭州", "to_city": "重庆",
                  "cheapest_total": 480.0},
            "b": {"from_city": "杭州", "to_city": "郑州",
                  "cheapest_total": 290.0},
            "d": {"from_city": "杭州", "to_city": "曼谷",
                  "cheapest_total": 900.0},
        }},
    }}


class DayDropsTests(unittest.TestCase):
    def test_needs_two_days(self):
        self.assertEqual(day_drops({"days": {"2026-09-14": {}}}), [])
        self.assertEqual(day_drops({"days": {}}), [])

    def test_sharp_requires_both_gates(self):
        out = {d["route_id"]: d for d in day_drops(_hist())}
        self.assertIn("a", out)
        self.assertIn("b", out)
        self.assertNotIn("c", out)  # gone today, nothing to compare
        self.assertNotIn("d", out)  # no prev day sample
        self.assertTrue(out["a"]["sharp"])     # -20% and -120 >= gates
        self.assertFalse(out["b"]["sharp"])    # only -10 yuan
        self.assertEqual(out["a"]["delta"], -120.0)
        self.assertEqual(out["a"]["pct"], -20.0)

    def test_rise_never_sharp(self):
        h = {"days": {
            "2026-09-13": {"routes": {"a": {"cheapest_total": 100.0}}},
            "2026-09-14": {"routes": {"a": {"cheapest_total": 300.0}}},
        }}
        d = day_drops(h)[0]
        self.assertEqual(d["delta"], 200.0)
        self.assertEqual(d["pct"], 200.0)
        self.assertFalse(d["sharp"])

    def test_abs_gate_blocks_small_absolute_dip(self):
        # -25% relative but only -25 yuan: blocked by the abs gate
        h = {"days": {
            "2026-09-13": {"routes": {"a": {"cheapest_total": 100.0}}},
            "2026-09-14": {"routes": {"a": {"cheapest_total": 75.0}}},
        }}
        self.assertFalse(day_drops(h)[0]["sharp"])
        self.assertTrue(day_drops(h, pct=15.0, abs_yuan=20.0)[0]["sharp"])


class DropsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import webui
        cls.client = webui.app.test_client()

    def test_drops_endpoint_contract(self):
        import webui
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "history.json"), "w",
                  encoding="utf-8") as f:
            json.dump(_hist(), f, ensure_ascii=False)
        old = webui.DATA_DIR
        webui.DATA_DIR = tmp
        try:
            r = self.client.get("/api/drops")
            self.assertEqual(r.status_code, 200)
            j = r.get_json()
            self.assertTrue(j["ok"])
            ids = {d["route_id"] for d in j["drops"]}
            self.assertEqual(ids, {"a", "b"})
            a = [d for d in j["drops"] if d["route_id"] == "a"][0]
            self.assertTrue(a["sharp"])
            self.assertEqual(a["today"], 480.0)
        finally:
            webui.DATA_DIR = old


if __name__ == "__main__":
    unittest.main()
