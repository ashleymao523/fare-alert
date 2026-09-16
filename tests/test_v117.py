# -*- coding: utf-8 -*-
"""v1.17: cabin alert pushes carry dep-arr times.

The user asked the business-cabin low-price module to be precise: a
push without departure/arrival times forces a re-check in the UI.
Both push paths now tail a '· HO1254 20:00-22:30' suffix - from the
observation itself, or borrowed from the zero-key schedule DB under
the v1.16 triple-match contract."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import evaluate_alert, push_time_suffix


SCHED = {
    "HO1254": {"dows": {
        "6": {"dep": "20:00", "arr": "22:30",
              "from": "北京", "to": "上海"},
    }},
}


class TestPushTimeSuffix(unittest.TestCase):
    def test_timed_row_uses_own_times_with_fno(self):
        row = {"fno": "CA1712", "dep": "08:30", "arr": "11:05"}
        self.assertEqual(
            push_time_suffix(row, SCHED, "北京", "杭州"),
            " · CA1712 08:30–11:05")

    def test_timeless_row_borrows_under_triple_match(self):
        row = {"date": "2026-10-11", "fno": "HO1254",  # a Sunday (6)
               "dep": "", "arr": ""}
        self.assertEqual(
            push_time_suffix(row, SCHED, "北京", "上海"),
            " · HO1254 20:00–22:30")
        self.assertEqual(row["tsrc"], "sched-borrow")

    def test_city_mismatch_returns_empty(self):
        row = {"date": "2026-10-11", "fno": "HO1254"}
        self.assertEqual(
            push_time_suffix(row, SCHED, "重庆", "上海"), "")
        self.assertNotIn("dep", row)

    def test_codeshare_suffix_uses_first_segment(self):
        row = {"date": "2026-10-11", "fno": "HO1254/CZ2326"}
        self.assertTrue(push_time_suffix(
            row, SCHED, "北京", "上海").startswith(" · HO1254 20:00"))

    def test_no_trustworthy_pair_stays_empty(self):
        row = {"date": "2026-10-13", "fno": "ZZ9999"}  # not in lib
        self.assertEqual(
            push_time_suffix(row, SCHED, "北京", "上海"), "")


class TestEvaluateAlertTimes(unittest.TestCase):
    def test_threshold_hit_carries_fno_dep_arr(self):
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-10-11", "cabin": "business",
                 "price": 1277.0, "fno": "HO1254",
                 "dep": "20:00", "arr": "22:30"}],
        }}}
        hits = evaluate_alert(
            hist, {"enabled": True, "threshold_total": 1500})
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["fno"], "HO1254")
        self.assertEqual(hits[0]["dep"], "20:00")
        self.assertEqual(hits[0]["arr"], "22:30")


class TestPushWiring(unittest.TestCase):
    def test_cabin_absorb_appends_suffix_on_both_paths(self):
        with open("main.py", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("push_time_suffix as cabin_push_ts", src)
        self.assertIn("历史新低(前低 ¥{q}){x}{t}", src)
        self.assertIn("(阈值 ¥{t}){s}", src)
        self.assertIn("cabin_push_ts(rec_hit, sched_db", src)
        self.assertIn("cabin_push_ts(h, sched_db", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
