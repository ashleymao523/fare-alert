# -*- coding: utf-8 -*-
"""v0.34 worker heartbeat tests: liveness file + /api/health exposure."""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import main as app_main  # noqa: E402
import webui  # noqa: E402


class WorkerHeartbeatTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_m = app_main.DATA_DIR
        self._orig_w = webui.DATA_DIR
        app_main.DATA_DIR = self._tmp.name
        webui.DATA_DIR = self._tmp.name

    def tearDown(self):
        app_main.DATA_DIR = self._orig_m
        webui.DATA_DIR = self._orig_w
        self._tmp.cleanup()

    def test_write_heartbeat_fields(self):
        app_main._write_heartbeat(True)
        p = os.path.join(self._tmp.name, "worker_heartbeat.json")
        with open(p, encoding="utf-8") as f:
            hb = json.load(f)
        self.assertTrue(hb["ok"])
        self.assertEqual(hb["pid"], os.getpid())
        self.assertLess(time.time() - hb["ts"], 5)

    def test_health_exposes_worker(self):
        app_main._write_heartbeat(True)
        with webui.app.test_client() as c:
            r = c.get("/api/health")
        self.assertEqual(r.status_code, 200)
        w = r.get_json().get("worker")
        self.assertIsNotNone(w)
        self.assertTrue(w["ok"])
        self.assertGreaterEqual(w["age_min"], 0.0)

    def test_health_without_heartbeat_is_null(self):
        with webui.app.test_client() as c:
            r = c.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json().get("worker"))


if __name__ == "__main__":
    unittest.main()
