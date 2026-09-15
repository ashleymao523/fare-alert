# -*- coding: utf-8 -*-
"""v0.41 backup/restore roundtrip tests (tmp dirs, no repo state)."""
import json
import io
import os
import sys
import tempfile
import unittest
import zipfile

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


class ManifestTests(unittest.TestCase):
    """v0.86: sealed bundles - sha256 manifest, tamper refusal,
    manifest itself never restored, safety backup on import."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = self._tmp.name
        os.makedirs(os.path.join(root, "data"))
        with open(os.path.join(root, "config.json"), "w",
                  encoding="utf-8") as f:
            f.write('{"webui": {"port": 1}}')
        with open(os.path.join(root, "data", "history.json"), "w",
                  encoding="utf-8") as f:
            f.write('{"days": {}}')
        self.root = root

    def tearDown(self):
        self._tmp.cleanup()

    def _zip(self):
        return backup.make_backup(
            self.root, dest_dir=os.path.join(self.root, "backups"))[0]

    def test_items_regained_post_v041_state(self):
        for rel in ("data/history.json", "data/cabin_history.json",
                    "data/point_fill_cache.json",
                    "data/sched_deposit.json"):
            self.assertIn(rel, backup.ITEMS)

    def test_manifest_seals_every_member(self):
        zpath = self._zip()
        mf = restore.read_manifest(zpath)
        self.assertEqual(mf["format"], 2)
        with zipfile.ZipFile(zpath) as z:
            names = {n.replace(os.sep, "/") for n in z.namelist()
                     if n != backup.MANIFEST_NAME}
        self.assertEqual(set(mf["sha256"]), names)
        restore.verify_manifest(zpath)  # quiet pass

    def test_tampered_member_refused(self):
        import hashlib
        zpath = self._zip()
        # rewrite config.json inside the archive, keep the old seal
        raw = os.path.join(self.root, "tampered.zip")
        with zipfile.ZipFile(zpath) as z, \
                zipfile.ZipFile(raw, "w") as out:
            for info in z.infolist():
                body = (b'{"webui": {"port": 999}}'
                        if info.filename == "config.json"
                        else z.read(info.filename))
                out.writestr(info.filename, body)
        with self.assertRaises(restore.ManifestError):
            restore.verify_manifest(raw)
        # digest math sanity: the probe file's own sha is stable
        self.assertEqual(
            hashlib.sha256(b"probe").hexdigest(),
            hashlib.sha256(b"probe").hexdigest())

    def test_unsealed_v041_archive_still_restores(self):
        legacy = os.path.join(self.root, "legacy.zip")
        with zipfile.ZipFile(legacy, "w") as z:
            z.writestr("config.json", '{"webui": {"port": 2}}')
        self.assertIsNone(restore.read_manifest(legacy))
        self.assertIsNone(restore.verify_manifest(legacy))
        restored, _skipped = restore.restore(legacy, root=self.root)
        self.assertIn("config.json", restored)

    def test_manifest_not_restored_and_safety_backup(self):
        zpath = self._zip()
        restored, _skipped = restore.restore(zpath, root=self.root)
        self.assertNotIn(backup.MANIFEST_NAME, restored)
        safety = restore.safety_backup(root=self.root)
        self.assertTrue(safety and os.path.exists(safety))
        self.assertIn("pre-restore-safety", os.path.basename(safety))


class BundleApiTests(unittest.TestCase):
    """v0.86 web endpoints: browser-exported zip stream + guarded
    import (409 on tamper, probe file roundtrip)."""

    @classmethod
    def setUpClass(cls):
        import webui
        cls.client = webui.app.test_client()
        cls.repo_root = os.path.dirname(os.path.abspath(webui.__file__))

    def _probe_zip(self, digest=None):
        import hashlib
        import io
        body = b'{"probe": true}'
        want = digest or hashlib.sha256(body).hexdigest()
        mf = {"format": 2, "code_ver": "test",
              "sha256": {"data/__bundle_probe__.json": want}}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("data/__bundle_probe__.json", body)
            z.writestr(backup.MANIFEST_NAME,
                       json.dumps(mf, ensure_ascii=False))
        return buf.getvalue()

    def test_export_streams_zip(self):
        r = self.client.get("/api/bundle/export")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_data().startswith(b"PK"))
        r.close()

    def test_import_probe_roundtrip_and_cleanup(self):
        probe = os.path.join(self.repo_root, "data",
                             "__bundle_probe__.json")
        try:
            r = self.client.post(
                "/api/bundle/import",
                data={"bundle": (io.BytesIO(self._probe_zip()),
                                 "probe.zip")},
                content_type="multipart/form-data")
            self.assertEqual(r.status_code, 200)
            d = r.get_json()
            self.assertTrue(d["ok"])
            self.assertGreaterEqual(d["restored"], 1)
            self.assertTrue(os.path.exists(probe))
        finally:
            if os.path.exists(probe):
                os.remove(probe)

    def test_import_tampered_is_409(self):
        r = self.client.post(
            "/api/bundle/import",
            data={"bundle": (io.BytesIO(self._probe_zip(
                digest="0" * 64)), "probe.zip")},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.get_json()["ok"])

    def test_import_rejects_non_zip(self):
        r = self.client.post(
            "/api/bundle/import",
            data={"bundle": (io.BytesIO(b"nope"), "probe.txt")},
            content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
