# -*- coding: utf-8 -*-
"""v1.09: keyless business-cabin patrol unit tests (pure, no IO)."""
import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.alerts import total_price
from core.booking_fill import fetch_lowest
from core.cabin_monitor import (
    booking_cabin_rows, default_config, probe_dates,
)
from core.flights import NON_REAL_SOURCES


class _FakeResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params or {})})
        return _FakeResp(self.payload)


def _payload():
    return {
        "aggregation": {
            "minPrice": {"units": "346", "nanos": 410000000},
            "totalCount": 15,
        },
        "flightOffers": [{
            "segments": [{
                "departureTime": "2026-10-15T08:05:00+08:00",
                "arrivalTime": "2026-10-15T11:20:00+08:00",
                "legs": [{
                    "flightInfo": {
                        "carrierInfo": {"marketingCarrier": "MF"},
                        "flightNumber": "8474",
                        "planeType": "738",
                    },
                }],
            }],
            "priceBreakdown": {"total": {
                "units": "346", "nanos": 410000000,
                "currencyCode": "EUR"}},
        }],
    }


class FetchLowestCabinTests(unittest.TestCase):
    def test_business_param_passthrough_and_parse(self):
        s = _FakeSession(_payload())
        got = fetch_lowest(s, {}, "HGH", "BKK", "2026-10-15",
                           offer_limit=3, cabin_class="BUSINESS")
        self.assertEqual(s.calls[0]["params"]["cabinClass"], "BUSINESS")
        self.assertEqual(got["total_eur"], 346.4)  # 1-dec rounding
        self.assertEqual(got["fno"], "MF8474")
        self.assertEqual(got["dep"], "08:05")
        self.assertEqual(got["arr"], "11:20")
        self.assertLessEqual(len(got["offers"]), 3)

    def test_default_stays_economy(self):
        s = _FakeSession(_payload())
        fetch_lowest(s, {}, "HGH", "BKK", "2026-10-15")
        self.assertEqual(s.calls[0]["params"]["cabinClass"], "ECONOMY")


class ProbeDatesTests(unittest.TestCase):
    RID = "patrol-重庆-杭州"

    def _hist(self):
        return {"routes": {self.RID: {"obs": [
            {"date": "2026-09-20", "cabin": "business",
             "price": 100, "ts": "2026-09-10T08:00"},
            {"date": "2026-09-25", "cabin": "business",
             "price": 90, "ts": "2026-09-12T08:00"},
        ]}}}

    def test_never_probed_first_then_stalest(self):
        out = probe_dates(self._hist(), self.RID,
                          "2026-09-18", "2026-09-27", k=10)
        self.assertEqual(out[:4], ["2026-09-18", "2026-09-19",
                                   "2026-09-21", "2026-09-22"])
        self.assertEqual(out[-2:], ["2026-09-20", "2026-09-25"])

    def test_k_truncation(self):
        out = probe_dates(self._hist(), self.RID,
                          "2026-09-18", "2026-09-27", k=2)
        self.assertEqual(out, ["2026-09-18", "2026-09-19"])

    def test_bad_window(self):
        self.assertEqual(probe_dates({}, self.RID, "junk", "x", k=6), [])
        self.assertEqual(probe_dates({}, self.RID,
                                     "2026-09-10", "2026-09-01"), [])


class BookingCabinRowsTests(unittest.TestCase):
    TAX = {"airport_fee": 50, "fuel_surcharge": 70}

    def test_roundtrip_tax_inclusive(self):
        got = {"total_eur": 346.4, "fno": "MF8474",
               "dep": "08:05", "arr": "11:20"}
        rows = booking_cabin_rows("2026-10-15", got, 120, 7.8)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r.source, "booking-cabin")
        self.assertEqual(r.cabin, "business")
        self.assertEqual(r.flight_no, "MF8474")
        self.assertEqual(r.dep_time, "08:05")
        self.assertEqual(r.arr_time, "11:20")
        self.assertEqual(total_price(r.bare_price, self.TAX), 2701.9)

    def test_guards(self):
        self.assertEqual(booking_cabin_rows("d", None, 120, 7.8), [])
        self.assertEqual(booking_cabin_rows("d", {}, 120, 7.8), [])
        self.assertEqual(
            booking_cabin_rows("d", {"total_eur": 0}, 120, 7.8), [])


class ConfigAndSemanticsTests(unittest.TestCase):
    def test_probe_dates_per_round_default(self):
        self.assertEqual(default_config()["probe_dates_per_round"], 6)

    def test_booking_cabin_is_real_source(self):
        # _cabin_absorb only keeps business rows whose source is NOT a
        # reference marker - booking-cabin must survive that filter.
        self.assertNotIn("booking-cabin", NON_REAL_SOURCES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
