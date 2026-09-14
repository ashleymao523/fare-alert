# -*- coding: utf-8 -*-
"""v0.44: offer-exact economy gap-fill (mocked session, no net)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.intl import fetch_fill_offers
from core.intl import _bump_usage, usage_snapshot
from main import _cached_fill_offers


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
        self.gets = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.gets.append(params)
        return _Resp(self._j)

    def post(self, url, data=None, headers=None, timeout=None):
        return _Resp({"access_token": "tok", "expires_in": 1799})


def _offer_j(total="880.00", dep="08:15", arr="10:50"):
    return {"data": [{
        "price": {"grandTotal": total},
        "itineraries": [{
            "duration": "PT2H35M",
            "segments": [{
                "carrierCode": "CA", "number": "1852",
                "departure": {"iataCode": "HGH",
                              "at": "2026-10-08T" + dep + ":00"},
                "arrival": {"iataCode": "CKG",
                            "at": "2026-10-08T" + arr + ":00"},
            }],
        }],
    }]}


class FillOffersTests(unittest.TestCase):
    def test_fetch_parses_economy_offer(self):
        s = _Session(_offer_j())
        with tempfile.TemporaryDirectory() as td:
            deals = fetch_fill_offers(
                s, {}, {"client_id": "x", "client_secret": "y"},
                {"airport_fee": 50, "fuel_surcharge": 70},
                "HGH", "CKG", ["2026-10-08"], td)
        self.assertEqual(len(deals), 1)
        d = deals[0]
        # grandTotal 880 is tax-inclusive -> bare = 880 - 120
        self.assertEqual(d.bare_price, 760.0)
        self.assertEqual(d.flight_no, "CA1852")
        self.assertEqual(d.dep_time, "08:15")
        self.assertEqual(d.arr_time, "10:50")
        self.assertEqual(d.source, "amadeus-fill")
        self.assertEqual(d.time_src, "amadeus")
        for p in s.gets:
            self.assertEqual(p["travelClass"], "ECONOMY")

    def test_fetch_caps_days(self):
        s = _Session(_offer_j())
        with tempfile.TemporaryDirectory() as td:
            fetch_fill_offers(
                s, {}, {"client_id": "x", "client_secret": "y"},
                {}, "HGH", "CKG",
                ["2026-10-%02d" % i for i in range(1, 11)], td)
        self.assertEqual(len(s.gets), 6)

    def test_cached_fill_offers_cache_hit_and_negative(self):
        s = _Session(_offer_j())
        gaps = ["2026-10-08", "2026-10-09"]
        with tempfile.TemporaryDirectory() as td:
            out1 = _cached_fill_offers(
                s, {}, {"tax": {}}, {"client_id": "x",
                                     "client_secret": "y"},
                "HGH", "CKG", gaps, td)
            self.assertEqual(len(out1), 2)  # same offer echo for both days
            self.assertEqual(len(s.gets), 2)
            # second call: everything cached, zero network gets
            out2 = _cached_fill_offers(
                s, {}, {"tax": {}}, {"client_id": "x",
                                     "client_secret": "y"},
                "HGH", "CKG", gaps, td)
            self.assertEqual(len(s.gets), 2)
            self.assertEqual(len(out2), 2)
            self.assertEqual(out2[0].dep_time, "08:15")
            # negative cache: a date the API had no offer for
            cache_path = os.path.join(td, "amadeus_fill_cache.json")
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
            self.assertIn("OFFER-HGH-CKG-2026-10-08", cache)
            # simulate negative entry, expect it honored (no row)
            cache["OFFER-HGH-CKG-2026-10-10"] = {"ts": 1e18, "p": None}
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f)
            out3 = _cached_fill_offers(
                s, {}, {"tax": {}}, {"client_id": "x",
                                     "client_secret": "y"},
                "HGH", "CKG", ["2026-10-10"], td)
            self.assertEqual(out3, [])
            self.assertEqual(len(s.gets), 2)

    def test_rotation_probes_beyond_first_batch(self):
        # v0.67: 12 holes with a 6-per-round budget must ALL be probed
        # across rounds - the old [:6] truncation starved holes #7+.
        s = _Session(_offer_j())
        gaps = ["2026-10-%02d" % i for i in range(1, 13)]  # 12 holes
        kw = {"tax": {}}
        ama = {"client_id": "x", "client_secret": "y"}
        with tempfile.TemporaryDirectory() as td:
            st1 = {}
            _cached_fill_offers(s, {}, kw, ama, "HGH", "CKG",
                                gaps, td, max_days=6, stats=st1)
            self.assertEqual(
                st1, {"holes": 12, "probed": 6, "deferred": 6})
            self.assertEqual(len(s.gets), 6)  # round 1: first 6 only
            # round 2: first 6 cached -> the next 6 rotate in
            st2 = {}
            out2 = _cached_fill_offers(s, {}, kw, ama, "HGH", "CKG",
                                       gaps, td, max_days=6, stats=st2)
            self.assertEqual(st2["probed"], 6)
            self.assertEqual(st2["deferred"], 0)
            self.assertEqual(len(s.gets), 12)
            self.assertEqual(len(out2), 12)  # 6 cached + 6 fresh
            # round 3: everything cached -> zero new probes
            st3 = {}
            _cached_fill_offers(s, {}, kw, ama, "HGH", "CKG",
                                gaps, td, max_days=6, stats=st3)
            self.assertEqual(st3["probed"], 0)
            self.assertEqual(len(s.gets), 12)

    def test_usage_counter_counts_and_rolls(self):
        import time as _t
        with tempfile.TemporaryDirectory() as td:
            _bump_usage(td, 2)
            n = _bump_usage(td)
            self.assertEqual(n, 3)
            snap = usage_snapshot(td)
            self.assertEqual(snap["today"], 3)
            self.assertIn(_t.strftime("%Y-%m-%d"), snap["days"])
            # seed 20 stale days -> only the newest 14 survive
            import json as _j
            path = os.path.join(td, "amadeus_usage.json")
            stale = {"days": {"2026-01-%02d" % d: d for d in range(1, 21)}}
            with open(path, "w", encoding="utf-8") as f:
                _j.dump(stale, f)
            _bump_usage(td)
            with open(path, encoding="utf-8") as f:
                days = _j.load(f)["days"]
            self.assertEqual(len(days), 14)  # rolling window incl. today

    def test_usage_endpoint_shape(self):
        import webui
        client = webui.app.test_client()
        r = client.get("/api/amadeus-usage")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertIn("today", j)
        self.assertIn("days", j)


if __name__ == "__main__":
    unittest.main()
