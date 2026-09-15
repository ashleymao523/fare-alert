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
                              offer_list,
                              coverage_stats,
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
        p["flightOffers"] = [
            # v0.94: 3U offer carries its own EUR total -> price_eur
            {"priceBreakdown": {"total": {
                "currencyCode": "EUR", "units": 158,
                "nanos": 610000000}},
             "segments": [{
                "departureTime": "2026-10-13T18:40:00",
                "arrivalTime": "2026-10-13T21:15:00",
                "legs": [{"flightInfo": {
                    "flightNumber": "2583",
                    "carrierInfo": {"marketingCarrier": "3U"},
                    "planeType": "738"}}],
                "travellerCheckedLuggage": [{"luggageAllowance": {
                    "luggageType": "CHECKED_IN", "maxTotalWeight": 20}}],
            }]},
            # no priceBreakdown on purpose: non-EUR / legacy offers
            # must degrade to price_eur=0, not break the parser
            {"segments": [{
                "departureTime": "2026-10-13T07:05:00",
                "arrivalTime": "2026-10-13T09:45:00",
                "legs": [{"flightInfo": {
                    "flightNumber": "8827",
                    "carrierInfo": {"marketingCarrier": "GJ"},
                    "planeType": "32N"}}],
            }]},
            {"segments": [{
                "departureTime": "2026-10-13T18:40:00",
                "arrivalTime": "2026-10-13T21:15:00",
                "legs": [{"flightInfo": {
                    "flightNumber": "2583",
                    "carrierInfo": {"marketingCarrier": "3U"},
                    "planeType": "738"}}],
            }]},
        ]
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

    def test_offer_list_parse_dedup_sort(self):
        from core.booking_fill import offer_list as ol
        rows = ol(_payload())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["no"], "GJ8827")   # 07:05 first
        self.assertEqual(rows[0]["dep"], "07:05")
        self.assertEqual(rows[0]["price_eur"], 0.0)  # no breakdown
        self.assertEqual(rows[1]["no"], "3U2583")
        self.assertEqual(rows[1]["dur"], "2h35m")
        self.assertEqual(rows[1]["price_eur"], 158.61)

    def test_deal_from_offers_priority(self):
        e = {"cny": 1273.0, "fno": "3U2583", "dep": "18:40",
             "arr": "21:15", "craft": "738",
            "offers": [{"no": "GJ8827", "dep": "07:05", "arr": "09:45",
                        "dur": "2h40m", "airline": "", "craft": "32N",
                        "via": "", "price_eur": 158.61}]}
        d = _deal_from(e, "2026-10-20", 120)
        self.assertEqual(len(d.alt_times), 1)
        self.assertEqual(d.alt_times[0]["no"], "GJ8827")
        self.assertEqual(d.alt_times[0]["src"], "booking")
        self.assertEqual(d.alt_times[0]["dur"], "2h40m")
        self.assertEqual(d.alt_times[0]["price"], 1237.0)  # *7.8

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
        self.assertTrue(real.alt_times)
        self.assertTrue(all(a.get("src") == "booking"
                            for a in real.alt_times))
        # v0.94: cached offers replay per-flight reference prices
        # (default fx 7.8 here, NOT the fill-time 8.0)
        self.assertEqual(real.alt_times[1]["no"], "3U2583")
        self.assertEqual(real.alt_times[1]["price"], 1237.0)
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

class TestBookingUpgrade(unittest.TestCase):
    """v0.90 legacy-quote timetable upgrade rotation."""

    def _dd(self):
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        return dd

    def _legacy_cache(self, dd):
        from core.booking_fill import _save
        _save(dd, {"rt1": {"2026-10-13": {
            "ts": time.time(), "cny": 1273.0, "dep": "18:40",
            "arr": "21:15", "dur": "2h35m", "fno": "3U2583"}}})

    def test_legacy_positive_reprobed_for_offers(self):
        dd = self._dd()
        self._legacy_cache(dd)
        s = _Session(_payload())
        cfg = {"booking_fill": {"fx_eur_cny": 8.0,
                                "max_per_cycle": 3, "call_interval": 0}}
        st = {}
        out = fill_gaps(s, {}, cfg, "HGH", "CKG", ["2026-10-13"],
                        120, dd, "rt1", stats=st,
                        sleeper=lambda x: None)
        self.assertEqual(st["probed"], 1)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].alt_times)
        self.assertTrue(all(a.get("src") == "booking"
                            for a in out[0].alt_times))
        with open(cache_path(dd), encoding="utf-8") as f:
            e = json.load(f)["rt1"]["2026-10-13"]
        self.assertTrue(e.get("offers"))
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_upgrade_failure_keeps_legacy_quote(self):
        dd = self._dd()
        self._legacy_cache(dd)
        s = _ErrSession({})
        cfg = {"booking_fill": {"fx_eur_cny": 8.0,
                                "max_per_cycle": 3, "call_interval": 0}}
        st = {}
        out = fill_gaps(s, {}, cfg, "HGH", "CKG", ["2026-10-13"],
                        120, dd, "rt1", stats=st,
                        sleeper=lambda x: None)
        # v0.93: a failed upgrade on a GAP date still replays the
        # cached quote (a stale GDS reference beats a grey dot), and
        # ts refreshes so the retry cools down for POS_TTL.
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].source, BOOKING_REF)
        self.assertAlmostEqual(out[0].bare_price, 1153.0)
        self.assertEqual(st["probed"], 1)
        self.assertEqual(st["deferred"], 1)
        with open(cache_path(dd), encoding="utf-8") as f:
            e = json.load(f)["rt1"]["2026-10-13"]
        self.assertEqual(e["cny"], 1273.0)
        self.assertEqual(e["dep"], "18:40")
        self.assertGreaterEqual(e["ts"], time.time() - 60)
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_zombie_4key_replays_cold_on_gap(self):
        # v0.93 fix B: a pre-v0.88 zombie entry (cny only, NO dep
        # key at all) must replay on gap dates WITHOUT a probe - the
        # live deadlock where far grey dates starved forever.
        dd = self._dd()
        from core.booking_fill import _save
        _save(dd, {"rt1": {"2026-11-05": {
            "ts": time.time(), "cny": 1862.0,
            "airline": "3U", "n": 378}}})
        s = _Session(_payload())
        cfg = {"booking_fill": {"fx_eur_cny": 8.0,
                                "max_per_cycle": 6, "call_interval": 0}}
        st = {}
        out = fill_gaps(s, {}, cfg, "HGH", "CKG", ["2026-11-05"],
                        120, dd, "rt1", stats=st,
                        sleeper=lambda x: None)
        self.assertEqual(st["probed"], 0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].dep_time, "")  # no itinerary yet
        self.assertAlmostEqual(out[0].bare_price, 1742.0)
        self.assertEqual(len(s.calls), 0)
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_gap_dates_outrank_extra_dates(self):
        # v0.93 fix A: with a 1-probe budget, a FAR gap date must be
        # probed before a NEAR extra date - the old flat sort() let
        # time-gaps eat the whole budget and starve grey dots.
        dd = self._dd()
        s = _Session(_payload())
        cfg = {"booking_fill": {"fx_eur_cny": 8.0,
                                "max_per_cycle": 1, "call_interval": 0}}
        st = {}
        fill_gaps(s, {}, cfg, "HGH", "CKG", ["2026-11-12"],
                  120, dd, "rt1", stats=st,
                  extra_dates=["2026-10-01", "2026-09-20"],
                  sleeper=lambda x: None)
        self.assertEqual(st["probed"], 1)
        self.assertEqual(len(s.calls), 1)
        self.assertIn("2026-11-12", str(s.calls[0].get("date", "")) or
                      str(s.calls[0]))
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_attach_replaces_unsourced_alts(self):
        dd = self._dd()
        from core.booking_fill import _save
        _save(dd, {"rt1": {"2026-10-13": {
            "ts": time.time(), "cny": 1273.0, "dep": "18:40",
            "arr": "21:15",
            "offers": [{"no": "GJ8827", "dep": "07:05",
                        "arr": "09:45", "dur": "2h40m"}]}}})
        d = FlightDeal(date="2026-10-13", bare_price=400.0,
                       flight_no="GJ8127",
                       alt_times=[{"no": "XX123", "dep": "12:00",
                                  "exact": False}])
        attach_times([d], dd, "rt1")
        self.assertEqual(len(d.alt_times), 1)
        self.assertEqual(d.alt_times[0]["no"], "GJ8827")
        self.assertEqual(d.alt_times[0]["src"], "booking")
        import shutil
        shutil.rmtree(dd, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

class TestCoverageStats(unittest.TestCase):
    """v0.91 timetable upgrade observability."""

    def test_mixed_cache_counts(self):
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        from core.booking_fill import _save, POS_TTL
        now = time.time()
        _save(dd, {
            "rt1": {
                # fresh positive WITH offers -> counted as covered
                "2026-10-01": {"ts": now, "cny": 900,
                               "offers": [{"no": "3U2583"}]},
                # fresh positive WITHOUT offers -> backlog
                "2026-10-02": {"ts": now, "cny": 800},
                # negative / expired -> ignored entirely
                "2026-10-03": {"ts": now, "cny": 0, "kind": "err"},
                "2026-10-04": {"ts": now - POS_TTL - 60, "cny": 700,
                               "offers": [{"no": "GJ8827"}]},
            },
            # malformed bucket must not crash the counter
            "rt2": "junk",
        })
        st = coverage_stats(dd)
        self.assertEqual(st["pos"], 2)
        self.assertEqual(st["offers"], 1)
        self.assertEqual(st["pending"], 1)
        self.assertEqual(st["pct"], 50)
        import shutil
        shutil.rmtree(dd, ignore_errors=True)


class TestBackfillPrices(unittest.TestCase):
    def _seed(self, dd):
        from core.booking_fill import _save
        _save(dd, {
            "rt1": {
                "2026-10-13": {"ts": time.time() - 100000,
                                "cny": 1200.0, "dep": "18:40",
                                "offers": [{"no": "3U2583", "dep": "18:40",
                                            "arr": "21:15",
                                            "dur": "2h35m"}]}},
            "rt2": {  # already priced -> skip
                "2026-10-14": {"ts": time.time(), "cny": 900.0,
                                "offers": [{"no": "GJ8827", "dep": "07:05",
                                            "arr": "09:45",
                                            "price_eur": 100.0}]}},
            "rt3": {  # negative -> skip, TTL intact
                "2026-10-15": {"ts": time.time(), "cny": 0,
                                "kind": "nodata"}},
        })

    def test_backfill_merge_and_skip(self):
        from core import booking_fill as bf
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        self._seed(dd)
        calls = []

        def fake_fetch(session, net_cfg, fi, ti, d):
            calls.append((fi, ti, d))
            # simulate a concurrent worker round writing mid-run
            cur = bf._load(dd)
            cur.setdefault("rt_concurrent", {})["2026-10-20"] = {
                "ts": time.time(), "cny": 777.0, "dep": "09:00",
                "offers": [{"no": "XX1", "dep": "09:00",
                            "price_eur": 99.0}]}
            bf._save(dd, cur)
            return {"total_eur": 158.61, "airline": "3U", "n_offers": 2,
                    "fno": "3U2583", "dep": "18:40", "arr": "21:15",
                    "dur": "2h35m", "stop_kind": "", "stop_city": "",
                    "stop_arr": "", "craft": "738", "bag": "20kg",
                    "offers": [{"no": "3U2583", "dep": "18:40",
                                "arr": "21:15", "dur": "2h35m",
                                "price_eur": 158.61}]}

        st = bf.backfill_prices(
            object(), {},
            {"booking_fill": {"fx_eur_cny": 7.8, "call_interval": 0}},
            dd, {"rt1": ("HGH", "CKG"), "rt2": ("HGH", "CGO"),
                 "rt3": ("HGH", "CTU")},
            sleeper=lambda x: None, fetch=fake_fetch)
        self.assertEqual(st["probed"], 1)
        self.assertEqual(st["priced"], 1)
        self.assertEqual(st["skipped"], 2)   # priced rt2 + negative rt3
        self.assertEqual(st["failed"], 0)
        self.assertEqual(calls, [("HGH", "CKG", "2026-10-13")])
        c = bf._load(dd)
        e1 = c["rt1"]["2026-10-13"]
        self.assertEqual(e1["cny"], 1237.0)  # 158.61 * 7.8
        self.assertEqual(e1["offers"][0]["price_eur"], 158.61)
        # concurrent write survived the merged save
        self.assertEqual(
            c["rt_concurrent"]["2026-10-20"]["cny"], 777.0)
        self.assertEqual(
            c["rt2"]["2026-10-14"]["offers"][0]["price_eur"], 100.0)
        import shutil
        shutil.rmtree(dd, ignore_errors=True)

    def test_backfill_budget_and_failure_keeps_entry(self):
        from core import booking_fill as bf
        dd = self.id() + str(int(time.time()))
        os.makedirs(dd, exist_ok=True)
        from core.booking_fill import _save
        old_ts = time.time() - 500
        _save(dd, {"rt1": {
            d: {"ts": old_ts, "cny": 1000.0 + i, "dep": "08:00",
                "offers": [{"no": "MF%04d" % i, "dep": "08:00"}]}
            for i, d in enumerate(("2026-10-13", "2026-10-14",
                                   "2026-10-15"))}})
        st = bf.backfill_prices(
            object(), {}, {"booking_fill": {"call_interval": 0}},
            dd, {"rt1": ("HGH", "CKG")}, max_n=2,
            sleeper=lambda x: None, fetch=lambda *a: None)
        self.assertEqual(st["probed"], 2)
        self.assertEqual(st["failed"], 2)
        self.assertEqual(st["deferred"], 1)
        c = bf._load(dd)["rt1"]
        for d in c:
            self.assertEqual(c[d]["ts"], old_ts)  # kept untouched
        import shutil
        shutil.rmtree(dd, ignore_errors=True)
