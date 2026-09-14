# -*- coding: utf-8 -*-
"""v0.60: alert-history kind classification + test-noise purge."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import core.notify as notify
from core.notify import classify_alert, _record_alert
import webui


class ClassifyTests(unittest.TestCase):
    def test_patterns(self):
        self.assertEqual(classify_alert("t"), "test")
        self.assertEqual(classify_alert(""), "test")
        self.assertEqual(classify_alert("✈️ FareAlert 测试推送"), "test")
        self.assertEqual(classify_alert("✈️FareAlert 测试推送"), "test")
        self.assertEqual(classify_alert("📈 FareAlert 价格周报"), "weekly")
        self.assertEqual(classify_alert("公务舱历史新低 重庆到杭州"), "cabin-record")
        self.assertEqual(classify_alert("公务舱低价 重庆到杭州"), "cabin")
        self.assertEqual(classify_alert("骤降提醒 杭州到重庆"), "drop")
        self.assertEqual(classify_alert("FareAlert 巡检异常"), "patrol")
        self.assertEqual(classify_alert("✈️杭州→重庆 低于¥500: ¥400 (09-20)"),
                         "threshold")
        self.assertEqual(classify_alert("别的什么东西"), "other")


class RecordKindTests(unittest.TestCase):
    def test_record_stores_explicit_and_fallback(self):
        fd, p = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(p)
        old = notify._ALERTS_FILE
        notify._ALERTS_FILE = p
        try:
            _record_alert("✈️杭州→重庆 低于¥500: ¥400 (09-20)", "b",
                          "", "r1", "threshold")
            _record_alert("t", "b", "", "")  # no kind -> classified test
            with open(p, encoding="utf-8") as f:
                rows = json.load(f)
            self.assertEqual(rows[0]["kind"], "threshold")
            self.assertEqual(rows[1]["kind"], "test")
        finally:
            notify._ALERTS_FILE = old
            if os.path.exists(p):
                os.remove(p)


class AlertsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = webui.app.test_client()

    def _patch(self, rows):
        fd, p = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
        old = webui.ALERTS_PATH
        webui.ALERTS_PATH = p

        def restore():
            webui.ALERTS_PATH = old
            if os.path.exists(p):
                os.remove(p)
        self.addCleanup(restore)
        return p

    def test_get_enriches_legacy_rows_and_counts(self):
        self._patch([
            {"ts": "2026-09-14T10:00", "title": "t", "body": "b"},
            {"ts": "2026-09-14T11:00",
             "title": "✈️A→B 低于¥500: ¥400 (09-20)", "body": "x"},
            {"ts": "2026-09-14T12:00", "title": "骤降提醒 A到B",
             "body": "y", "kind": "drop"},
        ])
        j = self.client.get("/api/alerts").get_json()
        kinds = sorted(a["kind"] for a in j["alerts"])
        self.assertEqual(kinds, ["drop", "test", "threshold"])
        self.assertEqual(j["counts"], {"test": 1, "threshold": 1, "drop": 1})

    def test_delete_purges_only_test_rows(self):
        p = self._patch([
            {"ts": "2026-09-14T10:00", "title": "t", "body": "b"},
            {"ts": "2026-09-14T10:01", "title": "t2", "body": "b"},
            {"ts": "2026-09-14T11:00",
             "title": "✈️A→B 低于¥500: ¥400 (09-20)", "body": "x"},
        ])
        r = self.client.delete("/api/alerts")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["removed"], 2)
        with open(p, encoding="utf-8") as f:
            leftover = json.load(f)
        self.assertEqual(len(leftover), 1)
        self.assertIn("低于¥", leftover[0]["title"])


if __name__ == "__main__":
    unittest.main()
