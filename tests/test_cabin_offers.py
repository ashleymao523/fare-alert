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

    def test_no_key_raises(self):
        s = _TokenSession({})
        with self.assertRaises(RuntimeError):
            fetch_cabin_offers(
                s, {}, {"client_id": "", "client_secret": ""},
                {}, "HGH", "CKG", "2026-10-01", "2026-10-02")


if __name__ == "__main__":
    unittest.main()
