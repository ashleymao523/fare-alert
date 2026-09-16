# -*- coding: utf-8 -*-
"""v1.12 tests: cabin price sparkline projection + time-heat wiring."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import history_timetable


class SparkProjectionTests(unittest.TestCase):
    def test_spark_projection(self):
        # per-date MIN (two obs same day -> cheaper wins), date-asc,
        # fno-less legacy rows count (they carry a real price).
        h = {"routes": {"a": {"from_city": "杭州", "to_city": "重庆", "obs": [
            {"date": "2026-10-02", "price": 1500, "fno": "CA1856"},
            {"date": "2026-10-02", "price": 1300, "fno": "HU7255"},
            {"date": "2026-10-01", "price": 1200, "fno": ""},
        ], "lowest": 1200}}}
        groups = history_timetable(h)
        self.assertEqual(groups[0]["spark"],
                         [{"d": "2026-10-01", "p": 1200},
                          {"d": "2026-10-02", "p": 1300}])

    def test_spark_cap_30(self):
        h = {"routes": {"a": {"from_city": "A", "to_city": "B", "obs": [
            {"date": "2026-%02d-%02d" % (1 + i // 28, 1 + i % 28),
             "price": 1000 + i, "fno": "F%02d" % i}
            for i in range(40)
        ], "lowest": 1000}}}
        spark = history_timetable(h)[0]["spark"]
        self.assertEqual(len(spark), 30)
        self.assertEqual(spark[0]["d"], "2026-01-11")  # oldest 30 kept
        self.assertTrue(all(spark[i]["d"] < spark[i + 1]["d"]
                            for i in range(len(spark) - 1)))

    def test_spark_empty_history(self):
        self.assertEqual(history_timetable({"routes": {}}), [])


class WiringContractTests(unittest.TestCase):
    def test_webui_wires_heat_and_spark(self):
        with open(os.path.join("webui", "templates", "index.html"),
                  encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="timeHeat"', html)
        self.assertIn("time-heat-box", html)
        self.assertNotIn("tab-timeheat", html)  # stray section removed
        with open(os.path.join("webui", "static", "app.js"),
                  encoding="utf-8") as f:
            app = f.read()
        self.assertIn("function loadTimeHeat", app)
        self.assertIn("/api/time-coverage", app)
        self.assertIn("function cabinSpark", app)
        self.assertIn("cabinSpark(g)", app)
        with open(os.path.join("webui", "static", "style.css"),
                  encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".time-heat-box", css)
        self.assertIn(".cabin-spark-line", css)
        self.assertIn(".th-cell.exact", css)


if __name__ == "__main__":
    unittest.main()
