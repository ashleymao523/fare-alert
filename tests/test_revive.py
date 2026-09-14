# -*- coding: utf-8 -*-
"""v0.38 revive tests: supervisor window logic + task probe + health."""
import datetime
import os
import threading
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui  # noqa: E402
from core import revive  # noqa: E402


class ReviveSupervisorTests(unittest.TestCase):
    def setUp(self):
        for k in ("last_check", "last_start", "last_probe",
                  "started_pid", "last_error",
                  "last_stale_restart",
                  "patrol_enabled", "patrol_done_day", "patrol_last",
                  "patrol_last_error", "catchup_done_day"):
            revive._state[k] = None

    def test_stale_worker_hot_swapped_in_window(self):
        """v0.51: a worker heartbeat stamped with older code gets
        killed + relaunched immediately (root cause: autostart never
        restarted a live-but-stale worker, so deploys never landed)."""
        p0 = mock.patch.object(revive, "stale_code_running",
                               return_value=True)
        p1 = mock.patch.object(revive, "stop_loop")
        p2 = mock.patch.object(revive, "start_loop")
        with p0, p1 as st, p2 as sl:
            sl.return_value = 9001
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 7, 30))
        self.assertEqual(rv, "restarted-stale-code")
        st.assert_called_once()
        sl.assert_called_once_with("/repo")
        lsr = revive.supervisor_snapshot()["last_stale_restart"]
        self.assertEqual(lsr["to"], revive.CODE_VERSION)
        self.assertEqual(revive._state["started_pid"], 9001)

    def test_stale_worker_hot_swapped_out_of_window(self):
        """Deploys propagate within one 5-min pass even midday - not
        only during the 07:00 launch window."""
        p0 = mock.patch.object(revive, "stale_code_running",
                               return_value=True)
        p1 = mock.patch.object(revive, "stop_loop")
        p2 = mock.patch.object(revive, "start_loop")
        with p0, p1, p2 as sl:
            sl.return_value = 9002
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 15, 0))
        self.assertEqual(rv, "restarted-stale-code")
        self.assertEqual(revive._state["catchup_done_day"], "2026-09-14")

    def test_stale_swap_error_recorded_not_raised(self):
        p0 = mock.patch.object(revive, "stale_code_running",
                               return_value=True)
        p1 = mock.patch.object(revive, "stop_loop")
        p2 = mock.patch.object(revive, "loop_running",
                               return_value=True)
        p3 = mock.patch.object(revive, "start_loop",
                               side_effect=OSError("spawn denied"))
        with p0, p1, p2, p3:
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 7, 30))
        self.assertEqual(rv, "already-running")  # fell through safely
        self.assertIn("spawn denied", revive._state["last_error"])

    def test_stale_detected_for_old_heartbeat(self):
        p0 = mock.patch.object(revive, "_worker_code_ver",
                               return_value="0.48")
        p1 = mock.patch.object(revive, "loop_running",
                               return_value=True)
        with p0, p1:
            self.assertTrue(revive.stale_code_running("/repo"))

    def test_stale_cooldown_blocks_second_swap(self):
        revive._state["last_stale_restart"] = {
            "ts": time.time(), "from": "0.48", "to": revive.CODE_VERSION}
        p0 = mock.patch.object(revive, "_worker_code_ver",
                               return_value="0.48")
        p1 = mock.patch.object(revive, "loop_running")
        with p0, p1 as lr:
            self.assertFalse(revive.stale_code_running("/repo"))
        lr.assert_not_called()  # cooldown short-circuits before probing

    def test_pre_restart_heartbeat_never_killed_twice(self):
        """After a swap the old heartbeat lingers until the new
        worker's first pass finishes; that must not trigger a second
        kill of the fresh worker mid-pass."""
        revive._state["last_stale_restart"] = {
            "ts": time.time(), "from": "0.48", "to": revive.CODE_VERSION}
        p0 = mock.patch.object(revive, "_worker_code_ver",
                               return_value="0.48")
        p1 = mock.patch.object(revive, "_worker_hb_ts",
                               return_value=time.time() - 600)
        p2 = mock.patch.object(revive, "loop_running")
        with p0, p1, p2 as lr:
            self.assertFalse(revive.stale_code_running("/repo"))
        lr.assert_not_called()

    def test_stale_redetected_when_heartbeat_newer_than_swap(self):
        revive._state["last_stale_restart"] = {
            "ts": time.time() - 4000, "from": "0.48",
            "to": revive.CODE_VERSION}
        p0 = mock.patch.object(revive, "_worker_code_ver",
                               return_value="0.48")
        p1 = mock.patch.object(revive, "_worker_hb_ts",
                               return_value=time.time() - 300)
        p2 = mock.patch.object(revive, "loop_running",
                               return_value=True)
        with p0, p1, p2:
            self.assertTrue(revive.stale_code_running("/repo"))

    def test_stale_skips_absent_heartbeat_and_same_version(self):
        p1 = mock.patch.object(revive, "loop_running")
        with mock.patch.object(revive, "_worker_code_ver",
                               return_value=None), p1 as lr:
            self.assertFalse(revive.stale_code_running("/repo"))
        with mock.patch.object(
                revive, "_worker_code_ver",
                return_value=revive.CODE_VERSION), p1:
            self.assertFalse(revive.stale_code_running("/repo"))
        lr.assert_not_called()

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

    def test_catchup_revives_stale_heartbeat_out_of_window(self):
        """v0.41: a desktop that boots AFTER the 07:00 window still
        revives a >6h-stale worker once per day, so board dow coverage
        keeps growing on any boot schedule (observed freeze: 2/7)."""
        p0 = mock.patch.object(revive, "_worker_heartbeat_age_s")
        p1 = mock.patch.object(revive, "loop_running")
        p2 = mock.patch.object(revive, "start_loop")
        with p0 as hb, p1 as lr, p2 as sl:
            hb.return_value = 2.6 * 86400
            lr.return_value = False
            sl.return_value = 4321
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 15, 0))
        self.assertEqual(rv, "started-catchup")
        sl.assert_called_once_with("/repo")
        self.assertEqual(revive._state["catchup_done_day"], "2026-09-14")

    def test_catchup_skips_fresh_heartbeat_out_of_window(self):
        """A fresh (<6h) heartbeat outside the window waits for the
        normal 07:00 revive - no extra midday launch cycles."""
        p0 = mock.patch.object(revive, "_worker_heartbeat_age_s")
        p1 = mock.patch.object(revive, "loop_running")
        p2 = mock.patch.object(revive, "start_loop")
        with p0 as hb, p1 as lr, p2 as sl:
            hb.return_value = 900
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 15, 0))
        self.assertEqual(rv, "out-of-window")
        lr.assert_not_called()
        sl.assert_not_called()

    def test_catchup_runs_once_per_day(self):
        """After a catch-up revive the day is marked done: later passes
        never re-probe/re-start, even with the heartbeat still stale."""
        p0 = mock.patch.object(revive, "_worker_heartbeat_age_s")
        p1 = mock.patch.object(revive, "loop_running")
        p2 = mock.patch.object(revive, "start_loop")
        with p0 as hb, p1 as lr, p2 as sl:
            hb.return_value = 9 * 3600
            lr.return_value = False
            sl.return_value = 111
            rv1 = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 15, 0))
            rv2 = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 15, 5))
        self.assertEqual(rv1, "started-catchup")
        self.assertEqual(rv2, "out-of-window")
        sl.assert_called_once()

    def test_catchup_marks_done_when_already_running(self):
        p0 = mock.patch.object(revive, "_worker_heartbeat_age_s")
        p1 = mock.patch.object(revive, "loop_running")
        p2 = mock.patch.object(revive, "start_loop")
        with p0 as hb, p1 as lr, p2 as sl:
            hb.return_value = 7 * 3600
            lr.return_value = True
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 15, 0))
        self.assertEqual(rv, "already-running-catchup")
        sl.assert_not_called()
        self.assertEqual(revive._state["catchup_done_day"], "2026-09-14")

    def test_catchup_absent_heartbeat_waits_for_window(self):
        """No heartbeat file at all = nothing to compare; the normal
        07:00 window owns the first launch (no midday cold start)."""
        p0 = mock.patch.object(revive, "_worker_heartbeat_age_s",
                               return_value=None)
        p1 = mock.patch.object(revive, "loop_running")
        p2 = mock.patch.object(revive, "start_loop")
        with p0, p1 as lr, p2 as sl:
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 15, 0))
        self.assertEqual(rv, "out-of-window")
        lr.assert_not_called()
        sl.assert_not_called()

    def test_catchup_probe_error_leaves_day_unmarked(self):
        """A probe failure must not consume the day: the next 5-min
        pass retries instead of skipping the revive entirely."""
        p0 = mock.patch.object(revive, "_worker_heartbeat_age_s")
        p1 = mock.patch.object(
            revive, "loop_running", side_effect=OSError("no powershell"))
        p2 = mock.patch.object(revive, "start_loop")
        with p0 as hb, p1, p2 as sl:
            hb.return_value = 9 * 3600
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 14, 15, 0))
        self.assertEqual(rv, "probe-error")
        sl.assert_not_called()
        self.assertIsNone(revive._state["catchup_done_day"])

    def test_probe_error_tolerated(self):
        p1 = mock.patch.object(revive, "loop_running",
                               side_effect=OSError("no powershell"))
        p2 = mock.patch.object(revive, "start_loop")
        with p1, p2 as sl:
            rv = revive.supervise_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 7, 30))
        self.assertEqual(rv, "probe-error")
        sl.assert_not_called()

    def test_supervisor_first_check_immediate(self):
        """v0.39: the daemon thread must run its first pass right away,
        so /api/health shows a real last_check after a webui restart
        (no 5-minute observability blind spot)."""
        calls = []
        done = threading.Event()

        def fake_supervise(repo):
            calls.append("check")
            done.set()
            raise SystemExit  # BaseException: ends the daemon loop cleanly

        with mock.patch.object(revive, "supervise_once", side_effect=fake_supervise):
            revive.start_supervisor("/repo", enabled=True, interval_s=300,
                                    patrol=True)
            self.assertTrue(done.wait(timeout=2), "first check never ran")
        revive._state["thread"] = None
        revive._state["enabled"] = False
        revive._state["patrol_enabled"] = False
        self.assertEqual(calls, ["check"])

    def test_patrol_runs_once_per_day_in_window(self):
        with mock.patch("core.patrol.run_patrol") as rp:
            rp.return_value = {"verdict": "healthy", "notified": False,
                               "ts": "2026-09-12T09:05:00"}
            revive._state["patrol_enabled"] = True
            rv1 = revive.patrol_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 9, 5))
            rv2 = revive.patrol_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 9, 45))
            rv3 = revive.patrol_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 15, 0))
        self.assertEqual(rv1, "ran:healthy")
        self.assertEqual(rv2, "already-done")
        self.assertEqual(rv3, "out-of-window")
        rp.assert_called_once()
        snap = revive.supervisor_snapshot()["patrol"]
        self.assertTrue(snap["enabled"])
        self.assertEqual(snap["last"]["verdict"], "healthy")

    def test_patrol_error_marks_day_done_no_retry_storm(self):
        with mock.patch("core.patrol.run_patrol",
                        side_effect=OSError("webui down")) as rp:
            revive._state["patrol_enabled"] = True
            rv1 = revive.patrol_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 9, 10))
            rv2 = revive.patrol_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 9, 40))
        self.assertEqual(rv1, "error")
        self.assertEqual(rv2, "already-done")
        rp.assert_called_once()
        self.assertEqual(
            revive.supervisor_snapshot()["patrol"]["last"]["verdict"], "error")
        self.assertIn("webui down",
                      revive.supervisor_snapshot()["patrol"]["last_error"])

    def test_patrol_attaches_offline_time_fill(self):
        """v0.41: after the health pass, patrol replays snapshot times
        offline; the summary lands in supervisor_snapshot for the UI."""
        with mock.patch("core.patrol.run_patrol") as rp, \
             mock.patch("core.reenrich.reenrich_snapshot") as reen:
            rp.return_value = {"verdict": "healthy", "notified": False,
                               "ts": "2026-09-12T09:05:00"}
            reen.return_value = {"routes": 2, "dep_covered": 70,
                                 "dep_total": 80, "changed": True,
                                 "per_route": []}
            revive._state["patrol_enabled"] = True
            rv = revive.patrol_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 9, 5))
        self.assertEqual(rv, "ran:healthy")
        reen.assert_called_once_with("/repo")
        tf = revive.supervisor_snapshot()["patrol"]["last"]["time_fill"]
        self.assertEqual(tf["dep_covered"], 70)
        self.assertEqual(tf["dep_total"], 80)

    def test_patrol_time_fill_error_becomes_payload(self):
        with mock.patch("core.patrol.run_patrol") as rp, \
             mock.patch("core.reenrich.reenrich_snapshot",
                        side_effect=OSError("disk")):
            rp.return_value = {"verdict": "healthy", "notified": False,
                               "ts": "2026-09-12T09:05:00"}
            revive._state["patrol_enabled"] = True
            rv = revive.patrol_once(
                "/repo", now=datetime.datetime(2026, 9, 12, 9, 5))
        self.assertEqual(rv, "ran:healthy")  # patrol itself still passed
        tf = revive.supervisor_snapshot()["patrol"]["last"]["time_fill"]
        self.assertIn("disk", tf["error"])


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
                        return_value={"enabled": True, "window": "07:00-07:59",
                                      "patrol": {"enabled": True,
                                                 "window": "09:00-09:59"}})
        with p1, p2:
            with webui.app.test_client() as c:
                r = c.get("/api/health")
        self.assertEqual(r.status_code, 200)
        rv = r.get_json().get("revive")
        self.assertEqual(rv["task"], fake_task)
        self.assertTrue(rv["supervisor"]["enabled"])
        self.assertTrue(rv["supervisor"]["patrol"]["enabled"])


if __name__ == "__main__":
    unittest.main()
