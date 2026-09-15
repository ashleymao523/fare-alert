# -*- coding: utf-8 -*-
"""v0.80: /api/reverse-latest contract - pure cache read, sorted, taxed."""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


def _tmpdir():
    return tempfile.mkdtemp(prefix="fa_revlatest_")


class ReverseLatestTests(unittest.TestCase):
    def setUp(self):
        self.client = webui.app.test_client()
        self.dd = _tmpdir()
        self.old_dd, self.old_cfg = webui.DATA_DIR, webui.CONFIG_PATH
        cfg_path = os.path.join(self.dd, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"tax": {"airport_fee": 50, "fuel_surcharge": 70}}, f)
        now = time.time()
        cache = {
            "杭州->北京|2026-09-10~2026-10-09": {
                "ts": now - 3600, "bare": 320.0, "date": "2026-09-20",
                "flight_no": "SC7968", "url": "https://m.flight.qunar.com/x"},
            "杭州->广州|2026-09-10~2026-10-09": {
                "ts": now - 60, "bare": 280.0, "date": "2026-09-18",
                "flight_no": "CZ3802", "url": "https://m.flight.qunar.com/y"},
            "杭州->三亚|w": {"ts": now, "no_data": True},
            "bad-key": {"ts": now, "bare": 100.0},
        }
        with open(os.path.join(self.dd, "reverse_cache.json"), "w",
                  encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        webui.DATA_DIR = self.dd
        webui.CONFIG_PATH = cfg_path

    def tearDown(self):
        webui.DATA_DIR, webui.CONFIG_PATH = self.old_dd, self.old_cfg

    def test_shape_and_sort(self):
        r = self.client.get("/api/reverse-latest")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["ok"])
        self.assertEqual(j["count"], 2)
        # cheaper (280+120=400) first regardless of cache age
        self.assertEqual(j["hits"][0]["city"], "广州")
        self.assertEqual(j["hits"][0]["total_price"], 400)
        self.assertEqual(j["hits"][1]["city"], "北京")
        self.assertEqual(j["hits"][1]["total_price"], 440)

    def test_row_fields(self):
        j = self.client.get("/api/reverse-latest").get_json()
        h = j["hits"][0]
        for k in ("from", "city", "total_price", "bare_price", "date",
                  "flight_no", "airline", "url", "age_hours"):
            self.assertIn(k, h)
        self.assertEqual(h["from"], "杭州")
        self.assertEqual(h["airline"], "中国南方航空")
        self.assertTrue(h["age_hours"] is not None and h["age_hours"] < 1.0)

    def test_empty_cache_ok(self):
        with open(os.path.join(self.dd, "reverse_cache.json"), "w",
                  encoding="utf-8") as f:
            json.dump({}, f)
        j = self.client.get("/api/reverse-latest").get_json()
        self.assertTrue(j["ok"])
        self.assertEqual(j["count"], 0)
        self.assertEqual(j["hits"], [])


if __name__ == "__main__":
    unittest.main()
