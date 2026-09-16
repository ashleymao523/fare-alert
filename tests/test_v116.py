# -*- coding: utf-8 -*-
"""v1.16: cabin timetable time borrow from the zero-key schedule DB.

Business-cabin rows historically lack dep/arr because timed refills
ride the Booking gateway (429-blocked for days). The economy side
already holds a fresh per-flight weekday schedule library - same
flight no, same weekday, same city pair means the times transfer
exactly. These tests pin the precision contract."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import (borrow_sched_time, history_board,
                                history_timetable)


SCHED = {
    "HO1254": {"dows": {
        "5": {"dep": "19:45", "arr": "22:25", "from": "北京", "to": "上海"},
        "6": {"dep": "20:00", "arr": "22:30", "from": "北京", "to": "上海"},
    }},
    "CZ3502": {"dows": {
        "1": {"dep": "18:35", "arr": "16:00", "from": "北京", "to": "上海"},
    }},
}


def _hist():
    return {"routes": {"patrol-北京-上海": {
        "from_city": "北京", "to_city": "上海", "obs": [
            {"date": "2026-10-11", "fno": "HO1254", "price": 1277.2},
            {"date": "2026-10-18", "fno": "HO1254", "price": 1283.4},
        ]}}}


class TestBorrowSchedTime(unittest.TestCase):
    def test_triple_match_fills_dep_arr(self):
        row = {"date": "2026-10-11", "fno": "HO1254"}  # a Sunday (dow 6)
        self.assertTrue(borrow_sched_time(row, SCHED, "北京", "上海"))
        self.assertEqual(row["dep"], "20:00")
        self.assertEqual(row["arr"], "22:30")
        self.assertEqual(row["tsrc"], "sched-borrow")

    def test_city_mismatch_refuses_borrow(self):
        row = {"date": "2026-10-11", "fno": "HO1254"}
        self.assertFalse(borrow_sched_time(row, SCHED, "重庆", "上海"))
        self.assertNotIn("dep", row)

    def test_dow_gap_refuses_borrow(self):
        # HO1254 has no Monday entry in the library
        row = {"date": "2026-10-12", "fno": "HO1254"}
        self.assertFalse(borrow_sched_time(row, SCHED, "北京", "上海"))

    def test_codeshare_first_segment_borrows(self):
        row = {"date": "2026-10-13", "fno": "CZ3502/CZ2326"}  # a Tuesday
        self.assertTrue(borrow_sched_time(row, SCHED, "北京", "上海"))
        self.assertEqual(row["dep"], "18:35")

    def test_timed_row_never_touched(self):
        row = {"date": "2026-10-11", "fno": "HO1254",
               "dep": "07:00", "arr": "09:30"}
        self.assertFalse(borrow_sched_time(row, SCHED, "北京", "上海"))
        self.assertEqual(row["dep"], "07:00")  # real data kept


class TestTimetableWiring(unittest.TestCase):
    def test_timetable_borrows_and_counts(self):
        g = history_timetable(_hist(), sched=SCHED)[0]
        self.assertEqual(g["timed"], 2)
        self.assertEqual(g["borrowed"], 2)
        self.assertTrue(all(r["dep"] for r in g["rows"]))
        self.assertTrue(all(r["tsrc"] == "sched-borrow"
                            for r in g["rows"]))

    def test_timetable_without_sched_stays_timeless(self):
        g = history_timetable(_hist())[0]
        self.assertEqual(g["timed"], 0)
        self.assertEqual(g.get("borrowed", 0), 0)
        self.assertTrue(all(not r["dep"] for r in g["rows"]))

    def test_board_low_flight_gets_times(self):
        b = history_board(_hist(), sched=SCHED)[0]
        self.assertEqual(b["low_dep"], "20:00")
        self.assertEqual(b["low_arr"], "22:30")
        self.assertEqual(b["low_tsrc"], "sched-borrow")


class TestSourceWiring(unittest.TestCase):
    def test_webui_loads_sched_and_passes_it(self):
        src = open("webui.py", encoding="utf-8").read()
        self.assertIn("load_sched_db(DATA_DIR)", src)
        self.assertIn("cw_timetable(ch, sched=sched_flights)", src)
        self.assertIn("cw_board(ch, sched=sched_flights)", src)

    def test_ui_borrow_badge_and_timed_chip(self):
        js = open(os.path.join("webui", "static", "app.js"),
                  encoding="utf-8").read()
        css = open(os.path.join("webui", "static", "style.css"),
                   encoding="utf-8").read()
        self.assertIn('row.tsrc === "sched-borrow"', js)
        self.assertIn("cabin-tt-borrow", js)
        self.assertIn("cabin-timed-chip", js)
        self.assertIn(".cabin-tt-time em.cabin-tt-borrow", css)
        self.assertIn(".cabin-timed-chip", css)


if __name__ == "__main__":
    unittest.main(verbosity=2)
