# -*- coding: utf-8 -*-
"""v0.69: /api/day-schedule contract (per-date timetable strip)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


class DayScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = webui.app.test_client()
        cls._tmp = tempfile.TemporaryDirectory()
        cls._old = webui.DATA_DIR
        webui.DATA_DIR = cls._tmp.name
        db = {"updated": 1, "flights": {
            # monday: HGH -> BKK board row carries dep AND arr
            "GJ8021": {"dows": {"0": {"dep": "13:00", "arr": "17:30",
                                    "from": "杭州",
                                    "to": "曼谷素万那普机场"}}},
            # monday stopover row: arr empty by design, via carries the stop
            "JD8888": {"dows": {"0": {"dep": "15:00", "arr": "",
                                    "from": "杭州",
                                    "to": "曼谷素万那普机场",
                                    "via": "深圳", "via_arr": "17:00"}}},
            # sunday: CKG -> HGH return-board row
            "GJ8692": {"dows": {"6": {"dep": "07:20", "arr": "10:05",
                                    "from": "重庆", "to": "杭州"}}},
        }}
        with open(os.path.join(cls._tmp.name, "flight_sched_db.json"),
                  "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False)

    @classmethod
    def tearDownClass(cls):
        webui.DATA_DIR = cls._old
        cls._tmp.cleanup()

    def test_missing_params_400(self):
        r = self.client.get("/api/day-schedule")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.get_json()["ok"])

    def test_bad_date_400(self):
        r = self.client.get("/api/day-schedule?from=杭州"
                            "&to=曼谷&date=2026-13-99")
        self.assertEqual(r.status_code, 400)

    def test_outbound_strip_has_arr(self):
        # 2026-10-19 is a monday (weekday 0)
        r = self.client.get("/api/day-schedule?from=杭州"
                            "&to=曼谷&date=2026-10-19")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["ok"])
        self.assertTrue(j["covered"])
        row = j["rows"][0]
        self.assertEqual(row["no"], "GJ8021")
        self.assertEqual(row["dep"], "13:00")
        self.assertEqual(row["arr"], "17:30")
        self.assertEqual(row["dur"], "4h30m")  # v0.74 exact duration
        self.assertTrue(row["exact"])

    def test_return_direction_uses_arrive_board(self):
        # 2026-10-25 is a sunday (weekday 6)
        r = self.client.get("/api/day-schedule?from=重庆"
                            "&to=杭州&date=2026-10-25")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        row = j["rows"][0]
        self.assertEqual(row["no"], "GJ8692")
        self.assertEqual(row["arr"], "10:05")

    def test_unknown_pair_empty_but_ok(self):
        r = self.client.get("/api/day-schedule?from=北京"
                            "&to=广州&date=2026-10-19")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["ok"])
        self.assertFalse(j["covered"])
        self.assertEqual(j["rows"], [])

    def test_full_count_and_via_fields(self):
        # v0.73: total/has_more expose the full deduped count;
        # stopover rows serialize via so chips can label them
        r = self.client.get("/api/day-schedule?from=杭州"
                            "&to=曼谷&date=2026-10-19")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["ok"])
        self.assertEqual(j["total"], 2)
        self.assertFalse(j["has_more"])
        via_rows = [x for x in j["rows"] if x["via"]]
        self.assertEqual(via_rows[0]["no"], "JD8888")
        self.assertEqual(via_rows[0]["via"], "深圳")
        # stopover rows have no final arr -> no invented duration
        self.assertEqual(via_rows[0]["dur"], "")


if __name__ == "__main__":
    unittest.main()
