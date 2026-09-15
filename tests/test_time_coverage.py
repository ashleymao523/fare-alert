# -*- coding: utf-8 -*-
"""time_coverage() classification tests (v0.21)."""
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.flights import NON_REAL_SOURCES, time_coverage
from core.models import FlightDeal


def deal(**kw):
    base = dict(date="2026-09-12", bare_price=300, flight_no="CA1234")
    base.update(kw)
    return FlightDeal(**base)


class TestTimeCoverage(unittest.TestCase):
    def test_exact_borrow_missing_dep(self):
        cov = time_coverage([
            deal(dep_time="08:00", time_src="amadeus"),
            deal(dep_time="09:30", time_src="airport-board"),
            deal(dep_time="10:00", time_src="airport-board-x"),
            deal(),
        ])
        self.assertEqual(cov["total"], 4)
        self.assertEqual(cov["dep_exact"], 2)
        self.assertEqual(cov["dep_borrow"], 1)
        self.assertEqual(cov["dep_missing"], 1)

    def test_arr_exact_est_missing(self):
        cov = time_coverage([
            deal(dep_time="08:00", arr_time="10:30", time_src="amadeus"),
            deal(dep_time="09:00", arr_time="11:00", time_src="airport-board-x"),
            deal(dep_time="12:00", arr_est="14:20"),
            deal(dep_time="13:00", time_src="airport-board"),
        ])
        self.assertEqual(cov["arr_exact"], 1)
        self.assertEqual(cov["arr_borrow"], 1)
        self.assertEqual(cov["arr_est"], 1)
        self.assertEqual(cov["arr_missing"], 1)

    def test_non_real_sources_excluded(self):
        cov = time_coverage([
            deal(source="nearby-ref", dep_time="08:00", time_src="amadeus"),
            deal(source="interp"),
            deal(dep_time="09:00", time_src="airport-board"),
        ])
        self.assertEqual(cov["total"], 1)
        self.assertEqual(cov["dep_exact"], 1)
        self.assertEqual(cov["dep_missing"], 0)

    def test_empty(self):
        cov = time_coverage([])
        self.assertEqual(cov["total"], 0)
        self.assertIn("dep_missing", cov)

    def test_per_field_sources_split(self):
        # v0.22: dep_src/arr_src classify each leg independently;
        # missing per-field src falls back to legacy time_src.
        cov = time_coverage([
            deal(dep_time="08:00", dep_src="amadeus",
                 arr_time="10:30", arr_src="airport-board-x"),
            deal(dep_time="09:00", time_src="amadeus",
                 arr_time="11:30"),
        ])
        self.assertEqual(cov["dep_exact"], 2)
        self.assertEqual(cov["arr_borrow"], 1)
        self.assertEqual(cov["arr_exact"], 1)

    def test_dep_borrow_arr_exact_mix(self):
        cov = time_coverage([
            deal(dep_time="08:00", dep_src="airport-board-x",
                 arr_time="10:30", arr_src="airport-board"),
        ])
        self.assertEqual(cov["dep_borrow"], 1)
        self.assertEqual(cov["arr_exact"], 1)

    def test_marker_tuple(self):
        self.assertEqual(NON_REAL_SOURCES, ("nearby-ref", "interp"))

    def test_promote_on_next_weekday(self):
        # v0.80: a borrowed row whose OWN date is a Sunday (2026-09-20)
        # can flip exact when the board lands that dow; from
        # today=2026-09-15 (Tuesday) the next Sunday is 2026-09-20.
        import datetime as _dt
        cov = time_coverage([
            deal(date="2026-09-20", dep_time="10:00",
                 time_src="airport-board-x", borrow_dow="2"),
        ], today=_dt.date(2026, 9, 15))
        self.assertEqual(cov["dep_borrow"], 1)
        self.assertEqual(cov["promote_on"], "2026-09-20")
        self.assertEqual(cov["promote_dow"], "6")

    def test_promote_on_picks_earliest_dow(self):
        # two own-date dows -> the nearer calendar date wins
        import datetime as _dt
        cov = time_coverage([
            deal(date="2026-09-20", dep_time="10:00",
                 time_src="airport-board-x"),  # next Sun = 09-20
            deal(date="2026-09-18", dep_time="12:00",
                 time_src="airport-board-x"),  # next Fri = 09-18
        ], today=_dt.date(2026, 9, 15))
        self.assertEqual(cov["promote_on"], "2026-09-18")
        self.assertEqual(cov["promote_dow"], "4")

    def test_promote_on_absent_without_borrow(self):
        import datetime as _dt
        cov = time_coverage([
            deal(dep_time="08:00", time_src="airport-board"),
        ], today=_dt.date(2026, 9, 15))
        self.assertEqual(cov["promote_on"], "")
        self.assertEqual(cov["dep_borrow"], 0)

    def test_promote_skips_landed_dows(self):
        # dows says Friday already has board data -> a Friday borrow row
        # stays un-promised (the source just lacks that flight); a
        # still-empty Sunday keeps its flip date.
        import datetime as _dt
        cov = time_coverage([
            deal(date="2026-09-18", dep_time="10:00",
                 time_src="airport-board-x"),
        ], today=_dt.date(2026, 9, 15), dows={"4": 500, "6": 0})
        self.assertEqual(cov["dep_borrow"], 1)
        self.assertEqual(cov["promote_on"], "")
        cov2 = time_coverage([
            deal(date="2026-09-20", dep_time="10:00",
                 time_src="airport-board-x"),
        ], today=_dt.date(2026, 9, 15), dows={"4": 500, "6": 0})
        self.assertEqual(cov2["promote_on"], "2026-09-20")


if __name__ == "__main__":
    unittest.main()
