# -*- coding: utf-8 -*-
"""v0.85: push text carries dep-arr times + borrow confidence marks.

The mobile threshold alert and the weekly global-best line share the
same helpers (dep_arr_text / conf_mark), so the phone sees the flight
window plus how trustworthy a borrowed time is - exact, N-dow
consensus, lone reference, or dows disagreeing."""
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.alerts import build_message, conf_mark, dep_arr_text
from core.models import FlightDeal
from core.weekly import global_best, global_best_line


def _deal(**kw):
    base = dict(date="2026-09-20", bare_price=380.0, flight_no="MU5100")
    base.update(kw)
    return FlightDeal(**base)


class TimeHelpers(unittest.TestCase):
    def test_window_both_dep_only_and_none(self):
        self.assertEqual(
            dep_arr_text(_deal(dep_time="07:45", arr_time="10:20")),
            "07:45-10:20")
        self.assertEqual(dep_arr_text(_deal(dep_time="07:45")), "07:45")
        self.assertEqual(dep_arr_text(_deal()), "")

    def test_marks_by_provenance(self):
        self.assertEqual(conf_mark(_deal(
            dep_time="07:45", time_src="airport-board")), "")
        self.assertEqual(conf_mark(_deal(
            dep_time="07:45", time_src="airport-board-x",
            borrow_dow="3")), "参考")
        self.assertEqual(conf_mark(_deal(
            dep_time="07:45", time_src="airport-board-x",
            borrow_dow="3", borrow_votes=3)), "3票")
        self.assertEqual(conf_mark(_deal(
            dep_time="07:45", time_src="airport-board-x",
            borrow_dow="3", borrow_unstable=True)), "⚠")
        self.assertEqual(conf_mark(_deal(
            dep_time="07:45", time_src="alt-ref")), "参考")

    def test_no_dep_never_marked(self):
        self.assertEqual(conf_mark(_deal(borrow_unstable=True)), "")

    def test_dict_shaped_snapshot_rows(self):
        row = {"dep_time": "06:35", "arr_time": "09:10",
               "time_src": "airport-board-x", "borrow_dow": "1",
               "borrow_votes": 4, "borrow_unstable": False}
        self.assertEqual(dep_arr_text(row), "06:35-09:10")
        self.assertEqual(conf_mark(row), "4票")


class BuildMessageTimes(unittest.TestCase):
    CFG = {"tax": {"airport_fee": 50, "fuel_surcharge": 70},
           "baggage_policy": {}}

    def _msg(self, d):
        route = {"from_city": "杭州", "to_city": "重庆",
                 "threshold_total": 500}
        return build_message(route, [(500.0, d)], [(500.0, d)], None,
                             self.CFG)

    def test_line_carries_exact_window_without_noise(self):
        _, body = self._msg(_deal(dep_time="07:45", arr_time="10:20",
                                  time_src="airport-board"))
        title, _ = self._msg(_deal(dep_time="07:45", arr_time="10:20",
                                   time_src="airport-board"))
        self.assertIn("(09-20 周日 07:45-10:20)", title)
        self.assertIn("07:45-10:20 裸价", body)
        self.assertNotIn("参考", body)

    def test_title_hides_thin_or_unstable_windows(self):
        lone_title, body = self._msg(_deal(
            dep_time="07:45", time_src="airport-board-x", borrow_dow="3"))
        self.assertEqual(lone_title,
                         "✈️杭州→重庆 低于¥500: ¥500 (09-20 周日)")
        self.assertIn("07:45(参考)", body)
        unstable_title, _ = self._msg(_deal(
            dep_time="07:45", time_src="airport-board-x", borrow_dow="3",
            borrow_unstable=True))
        self.assertEqual(unstable_title, lone_title)

    def test_line_marks_consensus_and_instability(self):
        _, body = self._msg(_deal(dep_time="07:45", arr_time="10:20",
                                  time_src="airport-board-x",
                                  borrow_dow="3", borrow_votes=3))
        self.assertIn("07:45-10:20(3票)", body)
        _, body2 = self._msg(_deal(dep_time="07:45",
                                   time_src="airport-board-x",
                                   borrow_dow="3",
                                   borrow_unstable=True))
        self.assertIn("07:45(⚠)", body2)


class ReferenceFlightLine(unittest.TestCase):
    """v1.00: push names the same-day cheapest booking-verified
    reference flight with its exact window - a concrete departure
    for dates whose OTA cheapest row still lacks one."""
    CFG = {"tax": {"airport_fee": 50, "fuel_surcharge": 70},
           "baggage_policy": {}}

    def _msg(self, d):
        route = {"from_city": "杭州", "to_city": "重庆",
                 "threshold_total": 500}
        return build_message(route, [(500.0, d)], [(500.0, d)], None,
                             self.CFG)

    def _alts(self):
        return [
            {"no": "HU7421", "dep": "13:10", "arr": "15:45",
             "src": "booking", "price": 2101, "exact": True},
            {"no": "3U2579", "dep": "06:50", "arr": "09:25",
             "src": "booking", "price": 1296, "exact": True},
            {"no": "GJ8827", "dep": "07:05", "arr": "09:45",
             "src": "booking", "price": 0, "exact": True},
            {"no": "SC4774", "dep": "23:05", "arr": "02:30",
             "src": "board", "price": 990, "exact": True},
        ]

    def test_reference_line_names_cheapest_booking_alt(self):
        d = _deal(alt_times=self._alts())   # OTA row: no dep at all
        _, body = self._msg(d)
        self.assertIn("当日班次参考: 3U2579 06:50-09:25 参考¥1296", body)
        self.assertNotIn("HU7421 13:10", body)

    def test_no_reference_line_without_booking_alts(self):
        d = _deal(dep_time="07:45", arr_time="10:20",
                  time_src="airport-board")
        _, body = self._msg(d)
        self.assertNotIn("当日班次参考", body)

    def test_alt_without_window_is_skipped(self):
        d = _deal(alt_times=[{"no": "3U2579", "dep": "", "arr": "",
                              "src": "booking", "price": 1296}])
        _, body = self._msg(d)
        self.assertNotIn("当日班次参考", body)


class WeeklyGlobalBestMarks(unittest.TestCase):
    def _gb(self, **extra):
        d = {"date": "2026-09-20", "total_price": 380,
             "dep_time": "19:45", "arr_time": "22:25"}
        d.update(extra)
        snap = {"routes": [
            {"id": "a", "from_city": "杭州", "to_city": "重庆",
             "threshold_total": 500, "deals": [d]}]}
        return global_best(snap)

    def test_consensus_votes_render(self):
        line = global_best_line(self._gb(
            time_src="airport-board-x", borrow_dow="3", borrow_votes=3))
        self.assertIn("(19:45-22:25·3票)", line)

    def test_unstable_warns(self):
        line = global_best_line(self._gb(
            time_src="airport-board-x", borrow_dow="3",
            borrow_unstable=True))
        self.assertIn("·⚠)", line)

    def test_exact_stays_clean(self):
        self.assertIn("(19:45-22:25)",
                      global_best_line(self._gb(time_src="airport-board")))


if __name__ == "__main__":
    unittest.main()
