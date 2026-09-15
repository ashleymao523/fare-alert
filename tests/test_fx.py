# -*- coding: utf-8 -*-
"""v0.99 fx chain: ECB daily rate resolution + booking EUR reprice."""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import fx
from core.booking_fill import _reprice_eur


class _Resp:
    def __init__(self, payload=None, text="", status=200):
        self._p = payload
        self.text = text
        self.status_code = status

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http %d" % self.status_code)


class _Session:
    """Configurable fake: maps url fragment -> (payload|text|exc)."""
    def __init__(self, frank=None, ecb=None):
        self.frank = frank
        self.ecb = ecb
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(url)
        if "frankfurter" in url:
            if isinstance(self.frank, Exception):
                raise self.frank
            return _Resp(payload=self.frank)
        if "ecb.europa" in url:
            if isinstance(self.ecb, Exception):
                raise self.ecb
            return _Resp(text=self.ecb)
        raise RuntimeError("unexpected url " + url)


class TestFxChain(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_frankfurter_primary(self):
        s = _Session(frank={"rates": {"CNY": 7.7489}, "date": "2026-09-14"})
        cfg = {"booking_fill": {"fx_mode": "ecb"}}
        out = fx.get_rate(s, cfg, self.dir, now=1000.0)
        self.assertEqual(out["source"], "frankfurter")
        self.assertAlmostEqual(out["rate"], 7.7489)
        self.assertFalse(out["stale"])
        # cache written: second resolve replay without any network
        s2 = _Session(frank=RuntimeError("down"), ecb=RuntimeError("down"))
        out2 = fx.get_rate(s2, cfg, self.dir, now=1000.0 + 3600)
        self.assertEqual(out2["source"], "frankfurter")
        self.assertFalse(out2["stale"])

    def test_ecb_official_fallback(self):
        s = _Session(frank=RuntimeError("403"),
                     ecb="KEY,OBS_VALUE,TIME_PERIOD\nEXR,7.7501,2026-09-15")
        out = fx.get_rate(s, {"booking_fill": {"fx_mode": "ecb"}},
                          self.dir, now=2000.0)
        self.assertEqual(out["source"], "ecb-official")
        self.assertAlmostEqual(out["rate"], 7.7501)

    def test_stale_cache_then_fallback(self):
        # nothing cached, both sources down -> configured fixed rate
        s = _Session(frank=RuntimeError("down"), ecb=RuntimeError("down"))
        out = fx.get_rate(s, {"booking_fill": {"fx_mode": "ecb",
                                    "fx_eur_cny": 7.6}},
                          self.dir, now=3000.0)
        self.assertEqual(out["source"], "fallback")
        self.assertAlmostEqual(out["rate"], 7.6)
        self.assertTrue(out["stale"])
        # now seed a stale cache entry: replay beats the fixed rate
        # (ts older than the 12h refresh window)
        with open(fx.cache_path(self.dir), "w", encoding="utf-8") as f:
            json.dump({"rate": 7.7, "source": "frankfurter",
                       "date": "2026-09-10",
                       "ts": 3000.0 - fx.FX_TTL_S - 3600.0}, f)
        out2 = fx.get_rate(s, {"booking_fill": {"fx_mode": "ecb"}},
                           self.dir, now=3000.0)
        self.assertTrue(out2["stale"])
        self.assertAlmostEqual(out2["rate"], 7.7)

    def test_fixed_mode_short_circuits(self):
        s = _Session()  # no calls allowed
        out = fx.get_rate(s, {"booking_fill": {"fx_mode": "fixed",
                                    "fx_eur_cny": 7.8}}, self.dir)
        self.assertEqual(out["source"], "fixed")
        self.assertAlmostEqual(out["rate"], 7.8)
        self.assertEqual(s.calls, [])

    def test_fresh_cache_no_network(self):
        cfg = {"booking_fill": {"fx_mode": "ecb"}}
        with open(fx.cache_path(self.dir), "w", encoding="utf-8") as f:
            json.dump({"rate": 7.75, "source": "frankfurter",
                       "date": "2026-09-15", "ts": time.time()}, f)
        s = _Session(frank=RuntimeError("down"), ecb=RuntimeError("down"))
        out = fx.get_rate(s, cfg, self.dir)
        self.assertFalse(out["stale"])
        self.assertAlmostEqual(out["rate"], 7.75)
        self.assertEqual(s.calls, [])  # fresh cache: zero network

    def test_reprice_eur(self):
        e = {"eur": 100.0, "cny": 780}
        _reprice_eur(e, 7.7489)
        self.assertEqual(e["cny"], 775.0)
        legacy = {"cny": 780}  # pre-v0.99 entry: untouched
        _reprice_eur(legacy, 7.7489)
        self.assertEqual(legacy["cny"], 780)
        bad = {"eur": "x"}
        _reprice_eur(bad, 7.7)  # must not raise


if __name__ == "__main__":
    unittest.main()
