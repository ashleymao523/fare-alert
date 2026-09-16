# -*- coding: utf-8 -*-
"""v1.10 precision tests: per-flight business-cabin timetable."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import (
    HISTORY_CAP, booking_cabin_rows, default_config, history_board,
    record_low)
from core.models import FlightDeal
from main import total_price


class TimetableRowsTests(unittest.TestCase):
    TAX = {"airport_fee": 50, "fuel_surcharge": 70}

    def test_offers_become_per_flight_rows(self):
        got = {
            "total_eur": 346.4, "fno": "MF8474",
            "dep": "08:05", "arr": "11:20",
            "offers": [
                {"no": "MF8474", "dep": "08:05", "arr": "11:20",
                 "price_eur": 346.4},
                {"no": "CA1856", "dep": "14:30", "arr": "17:45",
                 "price_eur": 402.6},
            ],
        }
        rows = booking_cabin_rows("2026-10-15", got, 120, 7.8)
        self.assertEqual(len(rows), 2)
        by = {r.flight_no: r for r in rows}
        self.assertEqual(by["MF8474"].dep_time, "08:05")
        self.assertEqual(by["CA1856"].arr_time, "17:45")
        for r in rows:
            self.assertEqual(r.cabin, "business")
            self.assertEqual(r.source, "booking-cabin")
        # tax-inclusive pay-total per flight, EUR*fx exactly
        self.assertAlmostEqual(
            total_price(by["MF8474"].bare_price, self.TAX),
            2701.9, places=1)
        self.assertAlmostEqual(
            total_price(by["CA1856"].bare_price, self.TAX),
            3140.3, places=1)

    def test_offer_junk_rows_skipped(self):
        got = {"offers": [
            {"no": "", "dep": "08:05", "price_eur": 300.0},
            {"no": "MU5137", "dep": "", "price_eur": 300.0},
            {"no": "MU5137", "dep": "09:10", "price_eur": 0},
            {"no": "MU5137", "dep": "09:10", "price_eur": "junk"},
            {"no": "SC2186", "dep": "19:40", "price_eur": 288.9},
        ]}
        rows = booking_cabin_rows("2026-10-16", got, 120, 7.8)
        self.assertEqual([r.flight_no for r in rows], ["SC2186"])

    def test_minprice_fallback_when_no_offers(self):
        got = {"total_eur": 346.4, "fno": "MF8474",
               "dep": "08:05", "arr": "11:20", "offers": []}
        rows = booking_cabin_rows("2026-10-15", got, 120, 7.8)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].flight_no, "MF8474")


class PerFlightHistoryTests(unittest.TestCase):
    def test_flights_coexist_same_date(self):
        h = {"routes": {}}
        e1 = record_low(h, "r", "北京", "杭州", "business",
                        "2026-10-01", 1800, fno="CA1501")
        e2 = record_low(h, "r", "北京", "杭州", "business",
                        "2026-10-01", 2100, fno="MU5137")
        obs = h["routes"]["r"]["obs"]
        self.assertEqual(len(obs), 2)
        self.assertFalse(e1.get("record"))
        self.assertFalse(e2.get("record"))
        self.assertEqual(h["routes"]["r"]["lowest"], 1800)

    def test_same_flight_replaces_anonymous_does_too(self):
        h = {"routes": {}}
        record_low(h, "r", "北京", "杭州", "business",
                   "2026-10-01", 1800, fno="CA1501")
        record_low(h, "r", "北京", "杭州", "business",
                   "2026-10-01", 1750, fno="CA1501")
        record_low(h, "r", "北京", "杭州", "business",
                   "2026-10-01", 999)          # legacy fno-less slot
        obs = h["routes"]["r"]["obs"]
        self.assertEqual(len(obs), 2)
        prices = sorted(o["price"] for o in obs)
        self.assertEqual(prices, [999, 1750])

    def test_record_low_tag_respects_flight_rows(self):
        h = {"routes": {}}
        record_low(h, "r", "北京", "杭州", "business",
                   "2026-10-01", 1800, fno="CA1501")
        e = record_low(h, "r", "北京", "杭州", "business",
                       "2026-10-02", 1600, fno="MU5137")
        self.assertTrue(e.get("record"))
        self.assertEqual(e.get("record_prev"), 1800)

    def test_defaults_and_board(self):
        cw = default_config()
        self.assertEqual(cw["probe_dates_per_round"], 12)
        self.assertGreaterEqual(HISTORY_CAP, 300)
        h = {"routes": {"r": {"from_city": "北京", "to_city": "杭州",
                              "obs": [
                                  {"date": "2026-10-01", "price": 1800,
                                   "fno": "CA1501", "ts": "t1"},
                                  {"date": "2026-10-02", "price": 1600,
                                   "fno": "MU5137", "ts": "t2"},
                              ], "lowest": 1600}}}
        board = history_board(h)
        self.assertEqual(board[0]["low_fno"], "MU5137")


if __name__ == "__main__":
    unittest.main()
