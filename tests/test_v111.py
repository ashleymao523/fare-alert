# -*- coding: utf-8 -*-
"""v1.11 tests: per-flight cabin timetable projection + dep/arr ring."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import (
    history_timetable, load_history, record_low)


H = {"routes": {}}


class RecordDepArrTests(unittest.TestCase):
    def test_entry_carries_dep_arr(self):
        h = {"routes": {}}
        e = record_low(h, "r", "北京", "杭州", "business",
                       "2026-10-11", 1277.2, fno="HO1254",
                       dep="06:55", arr="09:20")
        self.assertEqual(e["dep"], "06:55")
        self.assertEqual(e["arr"], "09:20")
        self.assertEqual(e["fno"], "HO1254")
        # legacy callers (no dep/arr) keep empty strings, not crashes
        e2 = record_low(h, "r", "北京", "杭州", "business",
                        "2026-10-11", 1300, fno="HO1258")
        self.assertEqual(e2["dep"], "")


class TimetableTests(unittest.TestCase):
    def test_projection_sorted_cheapest_first(self):
        h = {"routes": {
            "a": {"from_city": "北京", "to_city": "杭州", "obs": [
                {"date": "2026-10-11", "price": 1277.2, "fno": "HO1254",
                 "dep": "06:55", "arr": "09:20"},
                {"date": "2026-10-15", "price": 1549.6, "fno": "HO1258",
                 "dep": "08:00", "arr": "10:15"},
                {"date": "2026-10-01", "price": 1800, "fno": ""},
            ], "lowest": 1277.2},
            "b": {"from_city": "重庆", "to_city": "上海", "obs": [
                {"date": "2026-10-09", "price": 1943.5, "fno": "HO1250",
                 "dep": "09:10", "arr": "12:00"},
            ], "lowest": 1943.5},
        }}
        groups = history_timetable(h)
        self.assertEqual([g["route_id"] for g in groups], ["a", "b"])
        self.assertEqual(len(groups[0]["rows"]), 2)   # fno-less row dropped
        r0 = groups[0]["rows"][0]
        self.assertEqual(r0["fno"], "HO1254")
        self.assertEqual(r0["dep"], "06:55")
        self.assertEqual(r0["price"], 1277.2)

    def test_per_leg_cap_and_empty(self):
        h = {"routes": {"a": {"from_city": "A", "to_city": "B", "obs": [
            {"date": "2026-10-%02d" % i, "price": 1000 + i,
             "fno": "F%02d" % i} for i in range(1, 13)
        ], "lowest": 1001}}}
        groups = history_timetable(h, per_leg=8)
        self.assertEqual(len(groups[0]["rows"]), 8)
        self.assertEqual(groups[0]["rows"][0]["fno"], "F01")
        self.assertEqual(history_timetable({"routes": {}}), [])


class ApiCabinContractTests(unittest.TestCase):
    def test_webui_wires_timetable(self):
        src = open(os.path.join("webui.py"), encoding="utf-8").read()
        self.assertIn("history_timetable as cw_timetable", src)
        self.assertIn('"timetable": timetable', src)
        self.assertIn("cabinClass=BUSINESS", src)
        html = open(os.path.join("webui", "templates", "index.html"),
                    encoding="utf-8").read()
        self.assertIn('data-tab="cabin"', html)
        self.assertIn('id="cabinPanel"', html)
        app = open(os.path.join("webui", "static", "app.js"),
                   encoding="utf-8").read()
        self.assertIn("function loadCabin", app)
        self.assertIn('if (name === "cabin") loadCabin();', app)


if __name__ == "__main__":
    unittest.main()
