# -*- coding: utf-8 -*-
"""v1.15: 429 circuit breaker + fingerprint rotation unit tests."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import core.booking_fill as bf
from core.booking_fill import (
    bump_fingerprint, current_fingerprint, fetch_lowest, fill_gaps,
    warm_session)
from core.cabin_monitor import booking_cabin_rows


class _FakeResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


class _FakeSession:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": dict(headers or {})})
        return _FakeResp(self.payload, self.status)


class ThrottleMarkerTests(unittest.TestCase):
    def setUp(self):
        self._saved = bf._ua_idx
        bf._ua_idx = 0

    def tearDown(self):
        bf._ua_idx = self._saved

    def test_429_returns_throttled_marker(self):
        s = _FakeSession({"error": "Rate limit exceeded"}, status=429)
        got = fetch_lowest(s, {}, "HGH", "CKG", "2026-10-13")
        self.assertEqual(got, {"throttled": True})

    def test_503_still_none(self):
        s = _FakeSession({}, status=503)
        self.assertIsNone(fetch_lowest(s, {}, "HGH", "CKG", "2026-10-13"))

    def test_throttled_dict_yields_no_rows(self):
        rows = booking_cabin_rows("2026-10-13", {"throttled": True},
                                  120.0, 7.8)
        self.assertEqual(rows, [])

    def test_legacy_ua_is_config_pin_at_idx0(self):
        pinned = {"user_agent_desktop": "UA-PINNED/1.0"}
        self.assertEqual(current_fingerprint(pinned), "UA-PINNED/1.0")

    def test_bump_rotates_ua(self):
        first = current_fingerprint()
        second = bump_fingerprint()
        self.assertNotEqual(first, second)
        bf._ua_idx = 0

    def test_warm_session_hits_search_page(self):
        s = _FakeSession({}, status=200)
        code = warm_session(s)
        self.assertEqual(code, 200)
        self.assertIn("flights.booking.com", s.calls[0]["url"])


class FillGapBreakerTests(unittest.TestCase):
    def test_two_strikes_stop_the_batch(self):
        tmp = tempfile.mkdtemp(prefix="v115_")
        self.addCleanup(shutil.rmtree, tmp, True)
        calls = []

        def fake_fetch(session, net_cfg, fi, ti, d, **kw):
            calls.append(d)
            return {"throttled": True}

        orig = bf.fetch_lowest
        bf.fetch_lowest = fake_fetch
        self.addCleanup(setattr, bf, "fetch_lowest", orig)
        stats = {}
        dates = ["2026-10-%02d" % (13 + i) for i in range(5)]
        out = fill_gaps(_FakeSession({}), {}, {}, "HGH", "CKG",
                        dates, {"fuel": 0, "airport": 0}, tmp,
                        "rt-v115", stats=stats, sleeper=lambda s: None)
        self.assertEqual(out, [])
        self.assertEqual(len(calls), 2)       # breaker after 2nd 429
        self.assertEqual(stats["throttled"], 2)
        # no negative-cache pollution from a throttle
        import json
        cpath = os.path.join(tmp, "booking_fill_cache.json")
        cache = {}
        if os.path.exists(cpath):
            with open(cpath, encoding="utf-8") as f:
                cache = json.load(f)
        self.assertEqual(cache.get("rt-v115", {}), {})


class WiringTests(unittest.TestCase):
    def test_patrol_and_tool_breaker_wired(self):
        with open("main.py", encoding="utf-8") as f:
            main_src = f.read()
        with open(os.path.join("tools", "cabin_refill.py"),
                  encoding="utf-8") as f:
            tool_src = f.read()
        self.assertIn('got.get("throttled")', main_src)
        self.assertIn("booking_bump_fp()", main_src)
        self.assertIn('info["throttle"] = n_thr', main_src)
        self.assertIn("网关限流熔断", main_src)
        self.assertIn("circuit break", tool_src)
        self.assertIn("bump_fingerprint()", tool_src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
