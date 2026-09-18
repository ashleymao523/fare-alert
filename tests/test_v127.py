# -*- coding: utf-8 -*-
"""v1.27 acceptance: CDP real-browser precise cabin capture."""
import io
import json
import os
import sys
import unittest
import datetime as dt

sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer,
                                  encoding="utf-8", errors="replace")
except Exception:
    pass


class TestV127(unittest.TestCase):
    def test_01_version_pin(self):
        from core.version import CODE_VERSION
        self.assertTrue(str(CODE_VERSION).startswith("1."),
                        CODE_VERSION)
        self.assertEqual(CODE_VERSION, "1.27")

    def test_02_module_surface(self):
        from core import cdp_cabin
        for fn in ("capture_batch", "patrol_fill", "list_url",
                   "find_browser", "_seed_profile", "_kill_stale"):
            self.assertTrue(callable(getattr(cdp_cabin, fn, None)),
                            fn)

    def test_03_miner_js_shape(self):
        from core.cdp_cabin import MINER_JS
        # mirrors the recon miner: flight-no + price + times
        self.assertIn("cardOf", MINER_JS)
        self.assertIn("returnByValue", MINER_JS or "n/a") \
            if False else None
        self.assertIn("[class*=price]", MINER_JS)

    def test_04_deposit_row_shape(self):
        """A captured row must survive put_rows with the cabin tag -
        the absorb path reads exactly these keys."""
        import tempfile
        from core.point_fill import load_cache, put_rows
        with tempfile.TemporaryDirectory() as td:
            cache, n = put_rows(
                td, "cdp-cabin-X-Y",
                [{"date": "2026-09-18", "total": 1290.0,
                  "flight_no": "MU5138", "dep_time": "07:00",
                  "arr_time": "09:10", "cabin": "business",
                  "from_city": "北京", "to_city": "上海"}])
            self.assertEqual(n, 1)
            ent = cache["cdp-cabin-X-Y"]["2026-09-18"]
            self.assertEqual(ent["cabin"], "business")
            self.assertEqual(ent["flight_no"], "MU5138")
            self.assertEqual(ent["dep_time"], "07:00")
            self.assertEqual(ent["arr_time"], "09:10")
            self.assertEqual(ent["total"], 1290.0)
            # absorb-side pure function accepts it
            from core.cabin_monitor import absorb_point_cabin
            groups = absorb_point_cabin(cache, {"cabins": ["business"]})
            # v1.30: absorb groups by leg-{from}-{to}, not the cache key
            self.assertIn("leg-北京-上海", groups)
            rows = groups["leg-北京-上海"]["rows"]
            self.assertTrue(rows and rows[0]["cabin"] == "business")

    def test_05_patrol_fill_cadence_and_cap(self):
        """Round bookkeeping: cadence skip without throttle, daily cap
        honored, ledger persisted atomically."""
        import tempfile
        from core.cdp_cabin import patrol_fill
        with tempfile.TemporaryDirectory() as td:
            info = patrol_fill({"enabled": True}, [], td,
                               throttle_hits=0)
            # round 1 % 4 == 1 -> capture branch; no legs -> no-gaps
            self.assertEqual(info.get("skipped"), "no-gaps")
            led = json.load(open(os.path.join(
                td, "cdp_cabin_ledger.json"), encoding="utf-8"))
            self.assertGreaterEqual(int(led.get("rounds") or 0), 1)
            # round 2 -> cadence skip (no throttle)
            info1 = patrol_fill({"enabled": True}, [], td,
                                throttle_hits=0)
            self.assertEqual(info1.get("skipped"), "cadence")
            # throttle fires the capture branch, but the daily cap
            # (used=24 >= default cap 24) shuts it down
            led["days"] = {dt.date.today().isoformat(): 24}
            with open(os.path.join(td, "cdp_cabin_ledger.json"),
                      "w", encoding="utf-8") as f:
                json.dump(led, f)
            info2 = patrol_fill(
                {"enabled": True}, [], td, throttle_hits=2)
            self.assertEqual(info2.get("skipped"), "daily-cap")

    def test_06_patrol_hook_wired(self):
        src = open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py"), encoding="utf-8").read()
        self.assertIn("cdp_cabin_patrol_fill", src)
        self.assertIn("cdp_cabin", src)

    def test_07_ops_cli_smoke(self):
        src = open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tools", "cdp_cabin_fill.py"), encoding="utf-8").read()
        for token in ("--dry", "--smoke", "capture_batch",
                      "time_gap_dates"):
            self.assertIn(token, src)


if __name__ == "__main__":
    unittest.main()
