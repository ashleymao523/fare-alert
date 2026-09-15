# -*- coding: utf-8 -*-
"""v0.87 booking cross-fill: parse, budget, cache, merge semantics."""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.booking_fill import (BOOKING_REF, fill_gaps, fetch_lowest,
                               merge_booking_deals)
from core.flights import NON_REAL_SOURCES, window_dates
from core.models import FlightDeal
from core.point_fill import gap_dates, patch_snapshot_deals


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload

    def json(self):
        return self._p


class _Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(params)
        return _Resp(200, self.payload)


def _payload(units=163, nanos=430000000, airline="3U", n=208):
    return {"aggregation": {
        "totalCount": n,
        "minPrice": {"currencyCode": "EUR", "units": units,
                      "nanos": nanos},
        "stops": [{"cheapestAirline": {"code": airline}}],
    }}


class TestBookingFill(unittest.TestCase):
    def test_fetch_lowest_parse(self):
        s = _Session(_payload())
        got = fetch_lowest(s, {}, "HGH", "CKG", "2026-10-13")
        self.assertEqual(got["total_eur"], 163.4)
        self.assertEqual(got["airline"], "3U")
        self.assertEqual(got["n_offers"], 208)
        p = s.calls[0]
        self.assertEqual(p["from"], "HGH")
        self.assertEqual(p["depart"], "2026-10-13")

    def test_fill_gaps_budget_and_cache(self):
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        s = _Session(_payload())
        cfg = {"booking_fill": {"fx_eur_cny": 8.0, "max_per_cycle": 2,
                                "call_interval": 0}}
        gaps = ["2026-10-13", "2026-10-14", "2026-10-15"]
        st = {}
        out = fill_gaps(s, {"timeout_seconds": 5}, cfg, "HGH", "CKG",
                        gaps, 120, dd, "rt1", stats=st, sleeper=lambda x: None)
        self.assertEqual(st["probed"], 2)
        self.assertEqual(st["deferred"], 1)
        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(out[0].bare_price, 1187.0)
        self.assertEqual(out[0].source, BOOKING_REF)
        s2 = _Session(_payload())
        st2 = {}
        out2 = fill_gaps(s2, {}, cfg, "HGH", "CKG", gaps, 120, dd, "rt1",
                         stats=st2, sleeper=lambda x: None)
        self.assertEqual(len(s2.calls), 1)
        self.assertEqual(len(out2), 3)
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_merge_only_missing_dates(self):
        real = [FlightDeal(date="2026-10-13", bare_price=300.0,
                           flight_no="GJ8127")]
        bk = [FlightDeal(date="2026-10-13", bare_price=1300.0,
                         flight_no="3U8888"),
              FlightDeal(date="2026-10-15", bare_price=1187.0,
                         flight_no="3U8889", source=BOOKING_REF)]
        merged, n = merge_booking_deals(
            real, bk, lambda d: "http://ota/" + d)
        self.assertEqual(n, 1)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].date, "2026-10-13")
        self.assertEqual(merged[1].url, "http://ota/2026-10-15")

    def test_non_real_semantics(self):
        self.assertIn(BOOKING_REF, NON_REAL_SOURCES)
        from core.point_fill import load_cache, put_rows
        dd = self.id() + "c"
        os.makedirs(dd, exist_ok=True)
        put_rows(dd, "rt1", [{"date": "2026-10-15", "total": 500,
                              "flight_no": "3U8888", "dep_time": "07:30"}])
        snap = [{"date": "2026-10-15", "source": "booking-ref",
                 "bare_price": 1187.0, "total_price": 1307.0}]
        self.assertEqual(patch_snapshot_deals(snap, load_cache(dd), "rt1"), 1)
        self.assertEqual(snap[0]["source"], "point-fill")
        self.assertEqual(snap[0]["dep_time"], "07:30")
        gaps = gap_dates([{"date": "2026-10-15", "source": "booking-ref"},
                          {"date": "2026-10-16", "source": "interp"}],
                         ["2026-10-15", "2026-10-16"])
        self.assertEqual(gaps, ["2026-10-16"])
        import shutil
        shutil.rmtree(dd, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
