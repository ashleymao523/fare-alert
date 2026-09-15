# -*- coding: utf-8 -*-
"""v0.98: external webui watchdog - self-heal layer 4.

The three existing layers (webui-embedded supervisor, logon Startup
.cmd, daily 07:30 scheduled task) all LAUNCH things; nothing watches
the webui itself at runtime. If webui.py crashes midday the dashboard
and /api/* stay dark until the next logon - this script closes that
gap. Designed to run every 15 min from a scheduled task:

  healthy          -> reset fail counter, exit
  fail #1          -> count (one flaky poll must not restart)
  fail #2.. + cool -> run tools/restart_webui.ps1, start cooldown
  fail #2.. hot    -> hold (<=1 restart per 30 min, no storm)

State file data/watchdog_state.json is the source of truth surfaced
by /api/health (revive.runtime). Decision core is pure + unit-tested;
this file only does IO around it. Exit code is always 0 so the task
scheduler never flags a restart as a task failure.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HEALTH_URL = "http://127.0.0.1:8765/api/health"
STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "watchdog_state.json")
RESTART_PS1 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "restart_webui.ps1")
FAILS_BEFORE_RESTART = 2
COOLDOWN_S = 1800  # max one webui restart per 30 min


def decide(state, healthy, now):
    """Pure decision core (unit-tested): -> (action, new_state)."""
    st = dict(state or {})
    st["last_run"] = now
    if healthy:
        st["consecutive_fail"] = 0
        st["last_action"] = "healthy"
        return "healthy", st
    fails = int(st.get("consecutive_fail") or 0) + 1
    st["consecutive_fail"] = fails
    if fails < FAILS_BEFORE_RESTART:
        st["last_action"] = "counting"
        return "counting", st
    try:
        last_restart = float(st.get("last_restart") or 0)
    except (TypeError, ValueError):
        last_restart = 0.0
    # 0 = never restarted: no cooldown to honor (epoch-0 math would
    # wrongly hold a fresh watchdog for its first 30 minutes).
    if last_restart and now - last_restart < COOLDOWN_S:
        st["last_action"] = "cooldown"
        return "cooldown", st
    st["last_restart"] = now
    st["consecutive_fail"] = 0
    st["last_action"] = "restarting"
    return "restarting", st


def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            doc = json.load(f)
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _save_state(st):
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_PATH)
    except Exception:
        pass  # state file is best-effort; the decision still ran


def _probe():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def main():
    now = time.time()
    healthy = _probe()
    action, st = decide(_load_state(), healthy, now)
    if action == "restarting":
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy",
                 "Bypass", "-File", RESTART_PS1],
                capture_output=True, text=True, timeout=120)
        except Exception as e:
            st["last_action"] = "restart-error"
            st["last_error"] = str(e)[:200]
    _save_state(st)
    print(action)
    return 0


if __name__ == "__main__":
    sys.exit(main())
