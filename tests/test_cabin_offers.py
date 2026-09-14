# -*- coding: utf-8 -*-
"""v0.42: fetch_cabin_offers response parsing (mocked session, no net)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.intl import _spread_dates, fetch_cabin_offers


class _Resp:
    def __init__(self, j):
        self._j = j

    def raise_for_status(self):
        return None

    def json(self):
        return self._j


class _Session:
    def __init__(self, j):
        self._j = j
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(params)
        return _Resp(self._j)


class _TokenSession(_Session):
    def post(self, url, data=None, headers=None, timeout=None):
        return _Resp({"access_token": "tok", "expires_in": 1799})


class CabinOffersTests(unittest.TestCase):
    def test_spread_dates_bounds(self):
        self.assertEqual(_spread_dates("2026-10-01", "2026-10-03", 8),
                         ["2026-10-01", "2026-10-02", "2026-10-03"])
        self.assertEqual(_spread_dates("bad", "2026-10-03", 8), [])
        self.assertEqual(_spread_dates("2026-10-05", "2026-10-01", 8), [])

    def test_fetch_parses_best_offer(self):
        import tempfile
        j = {"data": [
            {"price": {"grandTotal": "1999.00"}},
            {"price": {"grandTotal": "1750.50"}},
            {"price": {"grandTotal": "2100.00"}},
        ]}
        s = _TokenSession(j)
        with tempfile.TemporaryDirectory() as td:
            deals = fetch_cabin_offers(
                s, {}, {"client_id": "x", "client_secret": "y"},
                {}, "HGH", "CKG", "2026-10-01", "2026-10-02",
                data_dir=td)
        self.assertEqual(len(deals), 2)
        self.assertEqual(deals[0].bare_price, 1750.5)
        self.assertEqual(deals[0].cabin, "business")
        self.assertEqual(deals[0].source, "amadeus-cabin")
        for p in s.calls:
            self.assertEqual(p["travelClass"], "BUSINESS")

    def test_fetch_extracts_exact_times_direct(self):
        """v0.43: single-segment offer -> offer-exact dep/arr + number."""
        import tempfile
        j = {"data": [{
            "price": {"grandTotal": "1680.00"},
            "itineraries": [{
                "duration": "PT2H35M",
                "segments": [{
                    "carrierCode": "CA", "number": "1852",
                    "departure": {"iataCode": "HGH",
                                  "at": "2026-10-01T07:45:00"},
                    "arrival": {"iataCode": "CKG",
                                "at": "2026-10-01T10:20:00"},
                }],
            }],
        }]}
        s = _TokenSession(j)
        with tempfile.TemporaryDirectory() as td:
            deals = fetch_cabin_offers(
                s, {}, {"client_id": "x", "client_secret": "y"},
                {}, "HGH", "CKG", "2026-10-01", "2026-10-01",
                data_dir=td)
        self.assertEqual(len(deals), 1)
        d = deals[0]
        self.assertEqual(d.flight_no, "CA1852")
        self.assertEqual(d.dep_time, "07:45")
        self.assertEqual(d.arr_time, "10:20")
        self.assertEqual(d.duration_text, "2h35m")
        self.assertEqual(d.time_src, "amadeus")
        self.assertEqual(d.dep_src, "amadeus")
        self.assertEqual(d.arr_src, "amadeus")
        self.assertEqual(d.stop_kind, "")

    def test_fetch_extracts_exact_times_connecting(self):
        """v0.43: multi-segment offer -> joined numbers + transfer leg."""
        import tempfile
        j = {"data": [{
            "price": {"grandTotal": "2200.00"},
            "itineraries": [{
                "duration": "PT5H10M",
                "segments": [
                    {"carrierCode": "MU", "number": "5458",
                     "departure": {"iataCode": "HGH",
                                   "at": "2026-10-01T13:05:00"},
                     "arrival": {"iataCode": "CSX",
                                 "at": "2026-10-01T15:10:00"}},
                    {"carrierCode": "CZ", "number": "3383",
                     "departure": {"iataCode": "CSX",
                                   "at": "2026-10-01T16:30:00"},
                     "arrival": {"iataCode": "CKG",
                                 "at": "2026-10-01T18:15:00"}},
                ],
            }],
        }]}
        s = _TokenSession(j)
        with tempfile.TemporaryDirectory() as td:
            deals = fetch_cabin_offers(
                s, {}, {"client_id": "x", "client_secret": "y"},
                {}, "HGH", "CKG", "2026-10-01", "2026-10-01",
                data_dir=td)
        d = deals[0]
        self.assertEqual(d.flight_no, "MU5458/CZ3383")
        self.assertEqual(d.dep_time, "13:05")
        self.assertEqual(d.arr_time, "18:15")
        self.assertEqual(d.stop_kind, "transfer")
        self.assertEqual(d.stop_city, "CSX")

    def test_fetch_times_absent_keeps_blank(self):
        """Legacy payload without itineraries still yields usable rows."""
        import tempfile
        j = {"data": [{"price": {"grandTotal": "1999.00"}}]}
        s = _TokenSession(j)
        with tempfile.TemporaryDirectory() as td:
            deals = fetch_cabin_offers(
                s, {}, {"client_id": "x", "client_secret": "y"},
                {}, "HGH", "CKG", "2026-10-01", "2026-10-01",
                data_dir=td)
        self.assertEqual(deals[0].dep_time, "")
        self.assertEqual(deals[0].time_src, "")

    def test_no_key_raises(self):
        s = _TokenSession({})
        with self.assertRaises(RuntimeError):
            fetch_cabin_offers(
                s, {}, {"client_id": "", "client_secret": ""},
                {}, "HGH", "CKG", "2026-10-01", "2026-10-02")


if __name__ == "__main__":
    unittest.main()
