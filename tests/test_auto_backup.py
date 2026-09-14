# -*- coding: utf-8 -*-
"""v0.75: core/auto_backup.py - daily guard + retention, all in tmp dirs."""
import glob
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.auto_backup import maybe_daily_backup


class AutoBackupTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="fa-bk-")
        self.data = os.path.join(self.root, "data")
        os.makedirs(self.data)
        with open(os.path.join(self.root, "config.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"routes": []}, f)
        with open(os.path.join(self.data, "snapshot.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"updated_at": "2026-09-14T00:00:00"}, f)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_created_then_skip_same_day(self):
        now = time.time()
        r1 = maybe_daily_backup(self.root, self.data, now=now)
        self.assertEqual(r1["status"], "created")
        zips = glob.glob(os.path.join(
            self.root, "backups", "fare-alert-backup-*.zip"))
        self.assertEqual(len(zips), 1)
        with open(os.path.join(self.data, "auto_backup.json"),
                  encoding="utf-8") as f:
            self.assertEqual(json.load(f)["date"], r1["date"])
        r2 = maybe_daily_backup(self.root, self.data, now=now + 60)
        self.assertEqual(r2["status"], "skip")
        self.assertEqual(len(glob.glob(os.path.join(
            self.root, "backups", "fare-alert-backup-*.zip"))), 1)

    def test_retention_keeps_newest_seven(self):
        bdir = os.path.join(self.root, "backups")
        os.makedirs(bdir, exist_ok=True)
        for i in range(9):
            p = os.path.join(bdir, "fare-alert-backup-2026090%d-000000.zip"
                             % (i + 1))
            with open(p, "wb") as f:
                f.write(b"x")
            os.utime(p, (1600000000 + i, 1600000000 + i))
        r = maybe_daily_backup(self.root, self.data)
        self.assertEqual(r["status"], "created")
        self.assertGreaterEqual(len(r["removed"]), 2)
        self.assertEqual(len(glob.glob(os.path.join(
            bdir, "fare-alert-backup-*.zip"))), 7)

    def test_never_raises_on_bad_root(self):
        r = maybe_daily_backup(os.path.join(self.root, "nope"), self.data)
        self.assertIn(r["status"], ("created", "error"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
