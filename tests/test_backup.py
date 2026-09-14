# -*- coding: utf-8 -*-
"""v0.41 backup/restore roundtrip tests (tmp dirs, no repo state)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import backup  # noqa: E402
import restore  # noqa: E402


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = self._tmp.name
        with open(os.path.join(root, "config.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"webui": {"port": 8765}}, f)
        os.makedirs(os.path.join(root, "data"))
        with open(os.path.join(root, "data", "snapshot.json"), "w",
                  encoding="utf-8") as f:
            f.write("{\"routes\": []}")
        os.makedirs(os.path.join(root, "data", "report", "wk1"))
        with open(os.path.join(root, "data", "report", "wk1",
                               "latest.json"), "w", encoding="utf-8") as f:
            f.write("{}")
        self.root = root

    def tearDown(self):
        self._tmp.cleanup()

    def test_roundtrip_carries_state(self):
        zpath, included, _skipped = backup.make_backup(
            self.root, dest_dir=os.path.join(self.root, "backups"))
        self.assertTrue(os.path.exists(zpath))
        self.assertIn("config.json", included)
        self.assertIn("data/snapshot.json", included)
        self.assertIn("data/report/", included)
        # wipe, restore, compare
        os.remove(os.path.join(self.root, "config.json"))
        os.remove(os.path.join(self.root, "data", "snapshot.json"))
        restored, skipped = restore.restore(zpath, root=self.root)
        self.assertGreaterEqual(len(restored), 3)
        self.assertEqual(skipped, [])
        with open(os.path.join(self.root, "config.json"),
                  encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["webui"]["port"], 8765)
        self.assertTrue(os.path.exists(os.path.join(
            self.root, "data", "report", "wk1", "latest.json")))

    def test_zip_slip_members_are_skipped(self):
        import zipfile
        evil = os.path.join(self.root, "evil.zip")
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("../../evil.txt", "pwn")
            z.writestr("config.json/../../../evil2.txt", "pwn")  # P1
            z.writestr("config.jsonx/../../evil3.txt", "pwn")    # prefix
            z.writestr("/abs/evil.txt", "pwn")
            z.writestr("C:/evil.txt", "pwn")                     # drive
            z.writestr("data/../config.json.bak", "pwn")
            z.writestr("data/ok.txt", "fine")
        restored, skipped = restore.restore(evil, root=self.root)
        self.assertEqual(restored, ["data/ok.txt"])
        for name in ("../../evil.txt", "config.json/../../../evil2.txt",
                     "config.jsonx/../../evil3.txt", "/abs/evil.txt",
                     "C:/evil.txt", "data/../config.json.bak"):
            self.assertIn(name, skipped)
        self.assertFalse(os.path.exists(os.path.join(
            self.root, "..", "..", "evil.txt")))

    def test_bad_member_does_not_abort_restore(self):
        """v0.41 review P2: one unwritable member is skipped, the rest
        of the archive still restores (no half-restore + traceback)."""
        import zipfile
        locked = os.path.join(self.root, "data", "locked.txt")
        with open(locked, "w", encoding="utf-8") as f:
            f.write("keep me")
        os.chmod(locked, 0o444)              # read-only: open(wb) fails
        zp = os.path.join(self.root, "mix.zip")
        with zipfile.ZipFile(zp, "w") as z:
            z.writestr("data/locked.txt", "overwrite attempt")
            z.writestr("data/fresh.txt", "fine")
        try:
            restored, skipped = restore.restore(zp, root=self.root)
            self.assertIn("data/fresh.txt", restored)
            self.assertIn("data/locked.txt", skipped)
            with open(locked, encoding="utf-8") as f:
                self.assertEqual(f.read(), "keep me")
        finally:
            os.chmod(locked, 0o666)  # before tearDown wipes the tmp dir


if __name__ == "__main__":
    unittest.main()
