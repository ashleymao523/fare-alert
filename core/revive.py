# -*- coding: utf-8 -*-
"""v0.38: worker daily self-heal (revive) engine + observability.

Why: the HKCU Run autostart only fires at logon. On a desktop that
stays logged in for weeks, a crashed (or never-started) worker loop
stays dead until the next logon - freezing board dow coverage and the
departure-time backfill that depends on it. Two revive layers:

1. supervisor thread inside the (always-on) webui process: during the
   daily 07:00 launch window it probes for a running "main.py --loop"
   and starts one if absent. Pure Python, cross-platform, needs no
   task-scheduler permissions (Register-ScheduledTask is denied for
   non-elevated sessions on hardened hosts - verified on the dev box).
2. optional per-user scheduled task (best-effort, registered by
   install_autostart.ps1 where the host allows it) running the same
   idempotent wrapper daily at 07:30.

v0.40 adds a second daily duty on the same supervisor thread: a 09:00
one-shot patrol (core.patrol) that health-checks the whole system and
reminds through the push channel only when something is wrong.

Both layers only ever LAUNCH the loop inside the morning window, so a
midday webui restart never adds extra fetch cycles beyond the normal
production cadence. /api/health surfaces both states so the dashboard
can tell "will self-heal tomorrow morning" from "needs manual action".
"""
import datetime
import json
import os
import subprocess
import sys
import threading
import time

TASK_NAME = "FareAlertWorkerRevive"
REVIVE_HOUR = 7          # launch window = 07:00-07:59 local time
PATROL_HOUR = 9          # patrol window = 09:00-09:59 local time
CHECK_INTERVAL_S = 300   # supervisor probe cadence

_PS_TASK_QUERY = (
    "try { $t = Get-ScheduledTask -TaskName '" + TASK_NAME + "' -ErrorAction Stop; "
    "$i = Get-ScheduledTaskInfo -TaskName '" + TASK_NAME + "'; "
    "@{ state = [string]$t.State; next = [string]$i.NextRunTime; "
    "last = [string]$i.LastRunTime; result = [string]$i.LastTaskResult } "
    "| ConvertTo-Json } catch { '' }")

_PS_PROC_QUERY = """(Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'"
 | Where-Object { $_.CommandLine -match 'main\\.py' -and $_.CommandLine -match '--loop' }
 | Select-Object -First 1).ProcessId"""

_state = {"enabled": False, "thread": None, "last_check": None,
          "last_start": None, "last_probe": None, "started_pid": None,
          "last_error": None,
          "patrol_enabled": False, "patrol_done_day": None,
          "patrol_last": None, "patrol_last_error": None}


def _query_task():
    """PowerShell probe seam (mock target for unit tests)."""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", _PS_TASK_QUERY],
        capture_output=True, text=True, timeout=6)
    s = (out.stdout or "").strip()
    return json.loads(s) if s else None


def task_status():
    """Best-effort revive-task state; never raises."""
    try:
        d = _query_task() or {}
    except Exception:
        return {"installed": False, "supported": True}
    if not d:
        return {"installed": False, "supported": True}
    return {
        "installed": True,
        "supported": True,
        "state": d.get("state") or None,
        "next_run": d.get("next") or None,
        "last_run": d.get("last") or None,
        "last_result": d.get("result") or None,
    }


def _in_launch_window(now=None):
    now = now or datetime.datetime.now()
    return now.hour == REVIVE_HOUR


def loop_running():
    """True when a 'main.py --loop' process exists (per-OS probe)."""
    if os.name == "nt":
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _PS_PROC_QUERY],
            capture_output=True, text=True, timeout=20)
        return bool((out.stdout or "").strip())
    out = subprocess.run(["pgrep", "-f", "main.py.*--loop"],
                         capture_output=True, text=True, timeout=10)
    return bool((out.stdout or "").strip())


def start_loop(repo_dir):
    """Launch a detached worker loop; returns its pid."""
    kw = {"cwd": repo_dir, "stdout": subprocess.DEVNULL,
          "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(
        [sys.executable, "-X", "utf8", "main.py", "--loop"], **kw)
    return p.pid


def supervise_once(repo_dir, now=None):
    """One supervision pass; returns the action taken (test seam)."""
    _state["last_check"] = time.time()
    if not _in_launch_window(now):
        return "out-of-window"
    try:
        running = loop_running()
    except Exception as e:
        _state["last_probe"] = "error"
        _state["last_error"] = str(e)
        return "probe-error"
    _state["last_probe"] = "ok"
    if running:
        return "already-running"
    _state["started_pid"] = start_loop(repo_dir)
    _state["last_start"] = time.time()
    return "started"


def patrol_once(repo_dir, now=None):
    """v0.40: one patrol pass inside the 09:00 window, once per day.

    A failed pass still marks the day done: the supervisor probes every
    5 minutes, and retrying a broken transport on every probe would turn
    a diagnostic into a request storm. Errors surface via
    supervisor_snapshot() instead.
    """
    from core.patrol import run_patrol
    now = now or datetime.datetime.now()
    if not _state.get("patrol_enabled"):
        return "disabled"
    if now.hour != PATROL_HOUR:
        return "out-of-window"
    day = now.date().isoformat()
    if _state.get("patrol_done_day") == day:
        return "already-done"
    try:
        doc = run_patrol(repo_dir, notify=True)
        _state["patrol_last"] = {"ts": doc.get("ts"),
                                 "verdict": doc.get("verdict"),
                                 "notified": doc.get("notified")}
        _state["patrol_done_day"] = day
        return "ran:" + (doc.get("verdict") or "?")
    except Exception as e:
        _state["patrol_last_error"] = str(e)
        _state["patrol_done_day"] = day
        return "error"


def start_supervisor(repo_dir, enabled=True, interval_s=CHECK_INTERVAL_S,
                     patrol=True):
    """Daemon thread driving supervise_once; idempotent, never raises."""
    if not enabled or _state["thread"]:
        return
    _state["enabled"] = True
    _state["patrol_enabled"] = bool(patrol)

    def _run():
        while True:
            try:
                supervise_once(repo_dir)
                patrol_once(repo_dir)
                # v0.39: first pass runs immediately, so /api/health shows
                # a real last_check right after a webui restart instead of
                # a 5-minute observability blind spot.
            except Exception as e:      # never kill the thread
                _state["last_error"] = str(e)
            time.sleep(interval_s)

    th = threading.Thread(target=_run, daemon=True, name="fare-revive")
    th.start()
    _state["thread"] = th


def supervisor_snapshot():
    return {"enabled": bool(_state["enabled"]),
            "window": "07:00-07:59",
            "last_check": _state["last_check"],
            "last_start": _state["last_start"],
            "last_probe": _state["last_probe"],
            "started_pid": _state["started_pid"],
            "patrol": {"enabled": bool(_state.get("patrol_enabled")),
                       "window": "09:00-09:59",
                       "last": _state.get("patrol_last"),
                       "last_error": _state.get("patrol_last_error")}}
