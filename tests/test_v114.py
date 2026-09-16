# -*- coding: utf-8 -*-
"""v1.14 tests: time-gap-first probing + coverage visibility."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import (
    history_timetable, probe_dates, time_gap_dates)


def _hist(routes):
    return {"routes": routes}


class ProbeTimeGapFirstTests(unittest.TestCase):
    RID = "patrol-北京-上海"

    def test_timeless_date_jumps_queue(self):
        # A: newest batch HAS dep/arr (fresh ts); B: newest batch is an
        # anonymous minPrice floor row (even fresher ts, no times);
        # C: never probed. Gap repair takes its budget share first:
        # B (gap) -> C (never) -> A (stale).
        h = _hist({self.RID: {"obs": [
            {"date": "2026-10-01", "ts": "2026-09-10T10:00:00",
             "price": 1200.0, "fno": "HO1254",
             "dep": "19:35", "arr": "22:00"},
            {"date": "2026-10-02", "ts": "2026-09-12T10:00:00",
             "price": 1100.0, "fno": "", "dep": "", "arr": ""},
        ]}})
        got = probe_dates(h, self.RID, "2026-10-01", "2026-10-03", k=3)
        self.assertEqual(
            got, ["2026-10-02", "2026-10-03", "2026-10-01"])

    def test_gap_budget_share_not_starved_by_never_probed(self):
        # 6 never-probed dates vs 3 gap dates, k=6: gaps claim half
        # the budget (3) instead of starving behind the rotation.
        obs = [{"date": "2026-10-0%d" % i, "ts": "2026-09-10T10:00:00",
                "price": 1100.0, "fno": "", "dep": "", "arr": ""}
               for i in (1, 2, 3)]
        h = _hist({self.RID: {"obs": obs}})
        got = probe_dates(h, self.RID, "2026-10-01", "2026-10-06", k=6)
        self.assertEqual(got[:3], ["2026-10-01", "2026-10-02",
                                   "2026-10-03"])
        self.assertEqual(
            got[3:], ["2026-10-04", "2026-10-05", "2026-10-06"])

    def test_legacy_ordering_kept_with_time_first_off(self):
        h = _hist({self.RID: {"obs": [
            {"date": "2026-10-01", "ts": "2026-09-10T10:00:00",
             "price": 1200.0, "fno": "HO1254",
             "dep": "19:35", "arr": "22:00"},
            {"date": "2026-10-02", "ts": "2026-09-12T10:00:00",
             "price": 1100.0, "fno": "", "dep": "", "arr": ""},
        ]}})
        got = probe_dates(h, self.RID, "2026-10-01", "2026-10-03", k=3,
                          time_first=False)
        # pure staleness: never-probed, then oldest ts first
        self.assertEqual(
            got, ["2026-10-03", "2026-10-01", "2026-10-02"])

    def test_same_batch_timed_row_marks_date_timed(self):
        # two obs share one probe ts; one carries times -> the date
        # counts as timed (no re-probe needed).
        h = _hist({self.RID: {"obs": [
            {"date": "2026-10-01", "ts": "2026-09-10T10:00:00",
             "price": 1500.0, "fno": "", "dep": "", "arr": ""},
            {"date": "2026-10-01", "ts": "2026-09-10T10:00:00",
             "price": 1600.0, "fno": "HO1258",
             "dep": "21:20", "arr": "23:30"},
            {"date": "2026-10-02", "ts": "2026-09-11T10:00:00",
             "price": 1100.0, "fno": "", "dep": "", "arr": ""},
        ]}})
        got = probe_dates(h, self.RID, "2026-10-01", "2026-10-02", k=2)
        self.assertEqual(got, ["2026-10-02", "2026-10-01"])

    def test_time_gap_dates_lists_only_window_gaps(self):
        h = _hist({self.RID: {"obs": [
            {"date": "2026-10-01", "ts": "2026-09-10T10:00:00",
             "price": 1200.0, "fno": "HO1254",
             "dep": "19:35", "arr": "22:00"},
            {"date": "2026-10-02", "ts": "2026-09-12T10:00:00",
             "price": 1100.0, "fno": "", "dep": "", "arr": ""},
            {"date": "2026-12-01", "ts": "2026-09-12T10:00:00",
             "price": 1100.0, "fno": "", "dep": "", "arr": ""},
        ]}})
        self.assertEqual(
            time_gap_dates(h, self.RID, "2026-10-01", "2026-10-05"),
            ["2026-10-02"])

    def test_cheap_timeless_fno_row_also_gaps(self):
        # newest batch for BOTH dates carries a timed row, but one
        # date's cheapest fno row is a timeless legacy capture - it
        # must still jump the re-probe queue (kind-b gap).
        h = _hist({self.RID: {"obs": [
            # 10-01: cheap HO1254 row has NO times (legacy point fill)
            {"date": "2026-10-01", "ts": "2026-09-10T10:00:00",
             "price": 1200.0, "fno": "HO1254", "dep": "", "arr": ""},
            # same date, newer batch, timed but pricier
            {"date": "2026-10-01", "ts": "2026-09-12T10:00:00",
             "price": 4550.0, "fno": "CZ8888",
             "dep": "19:35", "arr": "22:00"},
            # 10-02: fully healthy
            {"date": "2026-10-02", "ts": "2026-09-11T10:00:00",
             "price": 1300.0, "fno": "HO1258",
             "dep": "21:20", "arr": "23:30"},
        ]}})
        self.assertEqual(
            time_gap_dates(h, self.RID, "2026-10-01", "2026-10-02"),
            ["2026-10-01"])
        got = probe_dates(h, self.RID, "2026-10-01", "2026-10-02", k=2)
        self.assertEqual(got, ["2026-10-01", "2026-10-02"])


class TimetableCoverageTests(unittest.TestCase):
    def test_timetable_carries_timed_and_total(self):
        h = _hist({"patrol-北京-上海": {
            "from_city": "北京", "to_city": "上海",
            "obs": [
                {"date": "2026-10-11", "price": 1277.2, "fno": "HO1254",
                 "dep": "", "arr": "", "ts": "2026-09-10T10:00:00"},
                {"date": "2026-10-15", "price": 1283.4, "fno": "HO1250",
                 "dep": "11:40", "arr": "14:10",
                 "ts": "2026-09-11T10:00:00"},
                {"date": "2026-10-16", "price": 1290.0, "fno": "HO1248",
                 "dep": "19:15", "arr": "21:45",
                 "ts": "2026-09-12T10:00:00"},
            ]}})
        groups = history_timetable(h)
        self.assertEqual(len(groups), 1)
        g = groups[0]
        self.assertEqual(g["total"], 3)
        self.assertEqual(g["timed"], 2)

    def test_timed_obs_upgrades_timeless_twin(self):
        # same flight same date: cheap timeless legacy row vs newer
        # timed obs - the timed one must win the (date, fno) slot.
        h = _hist({"patrol-北京-上海": {
            "from_city": "北京", "to_city": "上海",
            "obs": [
                {"date": "2026-10-11", "price": 1277.2, "fno": "HO1254",
                 "dep": "", "arr": "", "ts": "2026-09-10T10:00:00"},
                {"date": "2026-10-11", "price": 1299.0, "fno": "HO1254",
                 "dep": "19:35", "arr": "22:00",
                 "ts": "2026-09-13T10:00:00"},
            ]}})
        groups = history_timetable(h)
        rows = groups[0]["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["dep"], "19:35")
        self.assertEqual(rows[0]["arr"], "22:00")
        self.assertEqual(groups[0]["timed"], 1)
        self.assertEqual(groups[0]["total"], 1)


class FrontWiringTests(unittest.TestCase):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _src(self, rel):
        with open(os.path.join(self.ROOT, rel), encoding="utf-8") as f:
            return f.read()

    def test_cabin_timetable_renders_coverage_chip(self):
        s = self._src(os.path.join("web", "src", "components",
                                   "CabinTimetable.jsx"))
        self.assertIn("cab-tt-cov", s)
        self.assertIn("g.timed", s)
        self.assertIn("g.total", s)

    def test_patrol_counts_time_refill(self):
        s = self._src("main.py")
        self.assertIn("cabin_time_gaps", s)
        self.assertIn('info["time_refill"]', s)


if __name__ == "__main__":
    unittest.main()
