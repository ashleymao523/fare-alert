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
                               merge_booking_deals, attach_times,
                               _deal_from, cache_path,
                               NEG_TTL_ERR, NEG_TTL_NODATA)
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
    p = {"aggregation": {
        "totalCount": n,
        "minPrice": {"currencyCode": "EUR", "units": units,
                      "nanos": nanos},
        "stops": [{"cheapestAirline": {"code": airline}}],
    }, "flightOffers": []}
    if n:
        p["flightOffers"] = [{"segments": [{
            "departureTime": "2026-10-13T18:40:00",
            "arrivalTime": "2026-10-13T21:15:00",
            "legs": [{"flightInfo": {
                "flightNumber": "2583",
                "carrierInfo": {"marketingCarrier": "3U"},
                "planeType": "738"}}],
            "travellerCheckedLuggage": [{"luggageAllowance": {
                "luggageType": "CHECKED_IN", "maxTotalWeight": 20}}],
        }]}]
    return p


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


class _ErrSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(params)
        return _Resp(503, self.payload)


class TestBookingExact(unittest.TestCase):
    """v0.88 exact itineraries + v0.88.1 negative-cache TTL split."""

    def test_fetch_no_data_vs_error(self):
        s = _Session({"aggregation": {"totalCount": 0}})
        got = fetch_lowest(s, {}, "HGH", "CKG", "2026-10-13")
        self.assertEqual(got, {"no_data": True})
        s2 = _ErrSession({})
        self.assertIsNone(fetch_lowest(s2, {}, "HGH", "CKG",
                                       "2026-10-13"))

    def test_neg_cache_split_ttl(self):
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        now = time.time()
        from core.booking_fill import _save
        _save(dd, {"rt1": {
            # expired err (age > NEG_TTL_ERR): re-probe, will succeed
            "2026-10-13": {"ts": now - NEG_TTL_ERR - 60, "cny": 0,
                           "kind": "err"},
            # fresh err: deferred
            "2026-10-14": {"ts": now - 600, "cny": 0, "kind": "err"},
            # fresh nodata: deferred (long TTL)
            "2026-10-15": {"ts": now - 600, "cny": 0,
                           "kind": "nodata"},
            # legacy negative without kind -> treated as err, expired
            "2026-10-16": {"ts": now - NEG_TTL_ERR - 60, "cny": 0},
        }})
        s = _Session(_payload())
        cfg = {"booking_fill": {"fx_eur_cny": 8.0, "max_per_cycle": 9,
                                "call_interval": 0}}
        st = {}
        out = fill_gaps(s, {}, cfg, "HGH", "CKG",
                        ["2026-10-13", "2026-10-14", "2026-10-15",
                         "2026-10-16"], 120, dd, "rt1", stats=st,
                        sleeper=lambda x: None)
        self.assertEqual(st["probed"], 2)
        self.assertEqual(st["deferred"], 2)
        self.assertEqual(len(out), 2)
        with open(cache_path(dd), encoding="utf-8") as f:
            c = json.load(f)["rt1"]
        self.assertGreater(c["2026-10-13"]["cny"], 0)
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_neg_cache_err_written_back(self):
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        s = _ErrSession({})
        cfg = {"booking_fill": {"fx_eur_cny": 8.0, "max_per_cycle": 3,
                                "call_interval": 0}}
        st = {}
        out = fill_gaps(s, {}, cfg, "HGH", "CKG", ["2026-10-13"],
                        120, dd, "rt1", stats=st,
                        sleeper=lambda x: None)
        self.assertEqual(out, [])
        with open(cache_path(dd), encoding="utf-8") as f:
            c = json.load(f)["rt1"]
        self.assertEqual(c["2026-10-13"]["kind"], "err")
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_offer_fields_to_deal(self):
        e = {"cny": 1273.0, "airline": "MF", "fno": "3U2583",
             "dep": "18:40", "arr": "21:15", "dur": "2h35m",
             "stop_kind": "", "stop_city": "", "stop_arr": "",
             "craft": "738", "bag": "20kg"}
        d = _deal_from(e, "2026-10-20", 120)
        self.assertEqual(d.dep_time, "18:40")
        self.assertEqual(d.arr_time, "21:15")
        self.assertEqual(d.dep_src, "booking")
        self.assertEqual(d.baggage_note, "20kg")
        self.assertEqual(d.alt_times[0]["no"], "3U2583")
        self.assertTrue(d.alt_times[0]["exact"])

    def test_extra_dates_cache_only_then_attach(self):
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        s = _Session(_payload())
        cfg = {"booking_fill": {"fx_eur_cny": 8.0, "max_per_cycle": 9,
                                "call_interval": 0}}
        st = {}
        out = fill_gaps(s, {}, cfg, "HGH", "CKG", ["2026-10-13"],
                        120, dd, "rt1", stats=st,
                        extra_dates=["2026-10-14"],
                        sleeper=lambda x: None)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].date, "2026-10-13")
        real = FlightDeal(date="2026-10-14", bare_price=400.0,
                          flight_no="GJ8127")
        st2 = {}
        attach_times([real], dd, "rt1", stats=st2)
        self.assertEqual(st2["attached"], 1)
        self.assertEqual(real.dep_time, "18:40")
        self.assertEqual(real.dep_src, "booking-x")
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_attach_times_policy(self):
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        from core.booking_fill import _save
        _save(dd, {"rt1": {"2026-10-13": {
            "ts": time.time(), "cny": 1273.0, "dep": "18:40",
            "arr": "21:15", "dur": "2h35m"}}})
        empty = FlightDeal(date="2026-10-13", bare_price=400.0,
                           flight_no="GJ8127")
        altref = FlightDeal(date="2026-10-13", bare_price=420.0,
                            flight_no="3U2583", dep_time="09:00",
                            dep_src="alt-ref", time_src="alt-ref")
        stats = {}
        attach_times([empty, altref], dd, "rt1", stats=stats)
        self.assertEqual(empty.dep_src, "booking-x")
        self.assertEqual(altref.dep_src, "alt-ref")
        self.assertEqual(altref.dep_time, "09:00")
        import shutil
        shutil.rmtree(dd, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
