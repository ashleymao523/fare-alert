# -*- coding: utf-8 -*-
"""v0.38 revive tests: supervisor window logic + task probe + health."""
import datetime
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui  # noqa: E402
from core import revive  # noqa: E402


class ReviveSupervisorTests(unittest.TestCase):
    def setUp(self):
        for k in ("last_check", "last_start", "last_probe",
                  "started_pid", "last_error"):
            revive._state[k] = None

    def test_out_of_window_never_starts(self):
        p1 = mock.patch.object(revive, "loop_running")
        p2 = mock.patch.object(revive, "start_loop")
        with p1 as lr, p2 as sl:
            lr.return_value = False
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 11, 15, 0))
        self.assertEqual(rv, "out-of-window")
        sl.assert_not_called()

    def test_in_window_starts_when_absent(self):
        p1 = mock.patch.object(revive, "loop_running")
        p2 = mock.patch.object(revive, "start_loop")
        with p1 as lr, p2 as sl:
            lr.return_value = False
            sl.return_value = 4242
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 7, 10))
        self.assertEqual(rv, "started")
        sl.assert_called_once_with("/repo")
        self.assertEqual(revive.supervisor_snapshot()["started_pid"], 4242)

    def test_in_window_skips_when_running(self):
        p1 = mock.patch.object(revive, "loop_running")
        p2 = mock.patch.object(revive, "start_loop")
        with p1 as lr, p2 as sl:
            lr.return_value = True
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 7, 59))
        self.assertEqual(rv, "already-running")
        sl.assert_not_called()

    def test_probe_error_tolerated(self):
        p1 = mock.patch.object(revive, "loop_running",
                               side_effect=OSError("no powershell"))
        p2 = mock.patch.object(revive, "start_loop")
        with p1, p2 as sl:
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 7, 30))
        self.assertEqual(rv, "probe-error")
        sl.assert_not_called()


class ReviveTaskTests(unittest.TestCase):
    def test_status_parses_task_info(self):
        with mock.patch.object(revive, "_query_task") as q:
            q.return_value = {"state": "Ready", "next": "2026-09-12 07:30:00",
                              "last": "", "result": "267009"}
            st = revive.task_status()
        self.assertTrue(st["installed"])
        self.assertEqual(st["state"], "Ready")
        self.assertEqual(st["next_run"], "2026-09-12 07:30:00")
        self.assertIsNone(st["last_run"])

    def test_status_absent_task(self):
        with mock.patch.object(revive, "_query_task", return_value=None):
            st = revive.task_status()
        self.assertFalse(st["installed"])
        self.assertTrue(st["supported"])

    def test_status_powershell_failure_tolerated(self):
        with mock.patch.object(revive, "_query_task",
                               side_effect=OSError("no powershell")):
            st = revive.task_status()
        self.assertFalse(st["installed"])
        self.assertTrue(st["supported"])

    def test_installer_registers_revive_best_effort(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, "tools", "install_autostart.ps1"),
                  encoding="utf-8-sig") as f:
            src = f.read()
        self.assertIn("FareAlertWorkerRevive", src)
        self.assertIn("-StartWhenAvailable", src)
        self.assertIn("-Daily", src)
        self.assertIn("task:FareAlertWorkerRevive", src)  # uninstall sweep
        self.assertIn("WARN: revive task registration denied", src)


class ReviveHealthTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = webui.DATA_DIR
        webui.DATA_DIR = self._tmp.name

    def tearDown(self):
        webui.DATA_DIR = self._orig
        self._tmp.cleanup()

    def test_health_exposes_revive_layers(self):
        fake_task = {"installed": False, "supported": True}
        p1 = mock.patch("core.revive.task_status", return_value=fake_task)
        p2 = mock.patch("core.revive.supervisor_snapshot",
                        return_value={"enabled": True, "window": "07:00-07:59"})
        with p1, p2:
            with webui.app.test_client() as c:
                r = c.get("/api/health")
        self.assertEqual(r.status_code, 200)
        rv = r.get_json().get("revive")
        self.assertEqual(rv["task"], fake_task)
        self.assertTrue(rv["supervisor"]["enabled"])


if __name__ == "__main__":
    unittest.main()
