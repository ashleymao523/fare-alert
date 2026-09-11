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

    def test_marker_tuple(self):
        self.assertEqual(NON_REAL_SOURCES, ("nearby-ref", "interp"))


if __name__ == "__main__":
    unittest.main()
