# -*- coding: utf-8 -*-
"""v1.15.1: adaptive 429 backoff unit tests (pure, temp dirs only)."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import patrol_gap
from core.agent_tasks import build_ledger


class PatrolGapTests(unittest.TestCase):
    def test_clean_round_resets_to_base(self):
        gap, streak = patrol_gap(1800, 3, 0)
        self.assertEqual(gap, 1800)
        self.assertEqual(streak, 0)

    def test_first_throttle_doubles(self):
        gap, streak = patrol_gap(1800, 0, 4)
        self.assertEqual(gap, 3600)
        self.assertEqual(streak, 1)

    def test_second_throttle_quadruples(self):
        gap, streak = patrol_gap(1800, 1, 2)
        self.assertEqual(gap, 7200)
        self.assertEqual(streak, 2)

    def test_third_throttle_caps_at_six(self):
        gap, streak = patrol_gap(1800, 2, 6)
        self.assertEqual(gap, 10800)
        self.assertEqual(streak, 3)
        gap2, _ = patrol_gap(1800, 5, 6)
        self.assertEqual(gap2, 10800)   # cap holds


class LedgerBackoffTests(unittest.TestCase):
    def test_card_uses_effective_cadence_mid_backoff(self):
        tmp = tempfile.mkdtemp(prefix="v1151_")
        self.addCleanup(shutil.rmtree, tmp, True)
        now = datetime(2026, 9, 16, 18, 0, 0)
        with open(os.path.join(tmp, "state.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"_cabin_patrol": {
                "last_run": "2026-09-16T17:55:00",
                "last_status": "standby · 网关限流熔断x4 · 限流退避下轮+120分",
                "throttle": 4, "throttle_streak": 2,
                "interval_effective_minutes": 120,
            }}, f, ensure_ascii=False)
        doc = build_ledger(tmp, {"cabin_watch": {
            "refresh_minutes": 30}}, now=now)
        ledger = doc["agents"]
        cp = next(a for a in ledger if a["id"] == "cabin-patrol")
        self.assertEqual(cp["cadence_minutes"], 120)
        self.assertEqual(cp["next_due"], "2026-09-16T19:55")
        self.assertEqual(cp["status"], "ok")   # not late mid-backoff

    def test_card_falls_back_to_base_when_clean(self):
        tmp = tempfile.mkdtemp(prefix="v1151c_")
        self.addCleanup(shutil.rmtree, tmp, True)
        now = datetime(2026, 9, 16, 18, 0, 0)
        with open(os.path.join(tmp, "state.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"_cabin_patrol": {
                "last_run": "2026-09-16T17:40:00",
                "throttle": 0, "interval_effective_minutes": 30,
            }}, f, ensure_ascii=False)
        doc = build_ledger(tmp, {"cabin_watch": {
            "refresh_minutes": 30}}, now=now)
        ledger = doc["agents"]
        cp = next(a for a in ledger if a["id"] == "cabin-patrol")
        self.assertEqual(cp["cadence_minutes"], 30)


class WiringTests(unittest.TestCase):
    def test_backoff_wired_end_to_end(self):
        with open("main.py", encoding="utf-8") as f:
            main_src = f.read()
        with open("webui.py", encoding="utf-8") as f:
            webui_src = f.read()
        self.assertIn("cabin_patrol_gap(base_s, prev_streak, n_thr)",
                      main_src)
        self.assertIn('info["interval_effective_minutes"]', main_src)
        self.assertIn('"interval_effective_minutes")', main_src)
        self.assertIn("限流退避下轮", main_src)
        self.assertIn('"interval_effective_minutes":', webui_src)
        self.assertIn('"throttle_streak":', webui_src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
