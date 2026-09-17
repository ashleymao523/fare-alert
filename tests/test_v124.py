# -*- coding: utf-8 -*-
"""v1.24 acceptance: business-cabin daily-lowest trend panel.

Covers the frontend surface (trend card, gradient area chart, threshold
line, hover crosshair, cache-bust v=32) and the timetable tsrc default
(timed patrol rows now always carry a source tag).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class TestV124(unittest.TestCase):
    def test_01_trend_frontend_surface(self):
        with open("webui/static/app.js", encoding="utf-8") as f:
            src = f.read()
        for needle in (
            "cabinTrendCard",
            "cabin-trend-svg",
            "linearGradient",
            "cabin-trend-line",
            "cabin-trend-dot-low",
            "cabin-trend-dot-high",
            "cabin-trend-th",
            "cabin-trend-xhair",
            "mousemove",
            "threshold_total",
        ):
            self.assertIn(needle, src, needle)

    def test_02_trend_css_tokens(self):
        with open("webui/static/style.css", encoding="utf-8") as f:
            src = f.read()
        for needle in (
            ".cabin-trend {",
            ".cabin-trend-svg",
            ".cabin-trend-line",
            ".cabin-trend-dot-low",
            ".cabin-trend-th",
            ".cabin-trend-tip {",
        ):
            self.assertIn(needle, src, needle)

    def test_03_index_cache_bust(self):
        with open("webui/templates/index.html", encoding="utf-8") as f:
            src = f.read()
        # v1.25+: version-specific pins live in the latest vX test only;
        # this suite asserts the cache-bust MECHANISM stays wired.
        self.assertRegex(src, r"style\.css\?v=\d+")
        self.assertRegex(src, r"app\.js\?v=\d+")
        self.assertRegex(src, r"v1\.\d+</span>")

    def test_04_timetable_tsrc_default(self):
        from core.cabin_monitor import history_timetable
        hist = {"routes": {"t-hgh": {
            "from_city": "北京", "to_city": "上海",
            "obs": [
                {"date": "2026-10-01", "cabin": "business",
                 "price": 1200.0, "fno": "MU5101",
                 "dep": "08:00", "arr": "10:20"},
                {"date": "2026-10-02", "cabin": "business",
                 "price": 1300.0, "fno": "MU5102"},
            ],
        }}}
        groups = history_timetable(hist)
        rows = {r["date"]: r for r in groups[0]["rows"]}
        self.assertEqual(rows["2026-10-01"]["tsrc"], "patrol")
        self.assertEqual(rows["2026-10-02"]["tsrc"], "")

    def test_05_version_bump(self):
        from core.version import CODE_VERSION
        # v1.25+: any 1.x is fine here; the exact pin lives in the
        # latest vX suite (test_v125 pins 1.25).
        self.assertTrue(CODE_VERSION.startswith("1."))


if __name__ == "__main__":
    unittest.main(verbosity=2)
