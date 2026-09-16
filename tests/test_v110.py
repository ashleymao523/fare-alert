# -*- coding: utf-8 -*-
"""v1.10 tests: agent task ledger (classify / next_due / build_ledger)."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.agent_tasks import _iso, build_ledger, classify, next_due


NOW = datetime(2026, 9, 16, 12, 0, 0)
ORDER = ["scan-all", "cabin-patrol", "dow-balance", "auto-backup",
         "fx-refresh", "health-patrol", "weekly-digest"]


class ClassifyTests(unittest.TestCase):
    def test_idle_when_never_ran(self):
        self.assertEqual(classify(None, 30, NOW), "idle")

    def test_ok_within_cadence(self):
        self.assertEqual(classify(NOW, 30, NOW), "ok")
        self.assertEqual(
            classify(datetime(2026, 9, 16, 11, 40), 30, NOW), "ok")

    def test_late_past_one_point_five_x(self):
        self.assertEqual(
            classify(datetime(2026, 9, 16, 10, 59), 30, NOW), "late")

    def test_clock_skew_counts_as_ok(self):
        self.assertEqual(
            classify(datetime(2026, 9, 16, 12, 10), 30, NOW), "ok")

    def test_next_due_math(self):
        self.assertIsNone(next_due(None, 30, NOW))
        self.assertEqual(
            next_due(datetime(2026, 9, 16, 11, 40), 30, NOW),
            "2026-09-16T12:10")

    def test_iso_eats_epoch_and_iso_strings(self):
        self.assertEqual(_iso(NOW.timestamp()), NOW)
        self.assertEqual(
            _iso("2026-09-16T11:50:30"),
            datetime(2026, 9, 16, 11, 50, 30))
        self.assertEqual(
            _iso("2026-09-16T11:50"), datetime(2026, 9, 16, 11, 50))
        self.assertIsNone(_iso("junk"))
        self.assertIsNone(_iso(None))


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def _write(self, name, payload):
        with open(os.path.join(self.dir, name), "w",
                  encoding="utf-8") as f:
            json.dump(payload, f)

    def test_empty_dir_all_idle_in_order(self):
        led = build_ledger(self.dir, {}, now=NOW)
        agents = led["agents"]
        self.assertEqual([a["id"] for a in agents], ORDER)
        self.assertTrue(all(a["status"] == "idle" for a in agents))
        self.assertTrue(led["updated_at"])

    def test_projection_from_real_files(self):
        self._write("worker_heartbeat.json", {
            "ts": NOW.timestamp() - 600, "pid": 42, "code_ver": "1.10"})
        self._write("state.json", {"_cabin_patrol": {
            "last_run": "2026-09-16T11:50:00",
            "last_status": "ok(booking-cabin)"}})
        self._write("fx_cache.json", {
            "ts": NOW.timestamp() - 23 * 3600, "rate": 7.7444,
            "source": "frankfurter", "date": "2026-09-15"})
        led = build_ledger(self.dir, {"cabin_watch": {
            "refresh_minutes": 30}}, now=NOW)
        by = {a["id"]: a for a in led["agents"]}
        scan = by["scan-all"]
        self.assertEqual(scan["status"], "ok")
        self.assertEqual(scan["age_min"], 10.0)
        self.assertEqual(scan["detail"], "worker pid 42 · code v1.10")
        self.assertEqual(scan["manual_trigger"], "/api/run")
        cp = by["cabin-patrol"]
        self.assertEqual(cp["status"], "ok")
        self.assertEqual(cp["next_due"], "2026-09-16T12:20")
        self.assertEqual(
            cp["manual_trigger"], "/api/tasks/cabin-patrol/run")
        fx = by["fx-refresh"]
        self.assertEqual(fx["status"], "ok")
        self.assertEqual(fx["next_due"], "2026-09-16T13:00")
        self.assertIn("7.7444", fx["detail"])
        self.assertIsNone(by["auto-backup"]["manual_trigger"])

    def test_auto_backup_late_after_37h(self):
        self._write("auto_backup.json", {
            "ts": NOW.timestamp() - 37 * 3600, "date": "2026-09-15",
            "items": 9})
        led = build_ledger(self.dir, {}, now=NOW)
        by = {a["id"]: a for a in led["agents"]}
        self.assertEqual(by["auto-backup"]["status"], "late")
        # 30h is still within 1.5x grace (36h)
        self._write("auto_backup.json", {
            "ts": NOW.timestamp() - 30 * 3600})
        led = build_ledger(self.dir, {}, now=NOW)
        by = {a["id"]: a for a in led["agents"]}
        self.assertEqual(by["auto-backup"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
