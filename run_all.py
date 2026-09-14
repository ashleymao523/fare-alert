# -*- coding: utf-8 -*-
"""v0.77 all-in-one container entrypoint: webui + worker loop in ONE
container, either child auto-respawned on crash.

Why: the old image ran webui.py only - a docker deployment had a pretty
UI but NO crawler, so the sched-board dow library never sedimented and
times stayed borrowed forever (the exact "no departure times" complaint).

Roles via FA_ROLE env: all (default) | webui | worker.
Logs of both children inherit this process' stdout -> docker logs shows
everything interleaved.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

PY = sys.executable


def build_cmds(role):
    """Pure role -> {name: argv} mapping (unit-tested, no side effects)."""
    role = (role or "all").strip().lower() or "all"
    if role not in ("all", "webui", "worker"):
        raise ValueError("FA_ROLE must be all | webui | worker, got %r" % role)
    cmds = {"webui": [PY, "webui.py"]}
    if role in ("all", "worker"):
        cmds["worker"] = [PY, "main.py", "--loop"]
    if role == "worker":
        cmds.pop("webui")
    return cmds


def log(msg):
    print("[run_all] %s" % msg, flush=True)


def main():
    role = os.environ.get("FA_ROLE", "all")
    try:
        cmds = build_cmds(role)
    except ValueError as e:
        log(str(e))
        sys.exit(2)
    log("role=%s -> %s" % (role, sorted(cmds)))
    running = {}
    try:
        while True:
            for name, argv in cmds.items():
                p = running.get(name)
                if p is not None and p.poll() is None:
                    continue
                if p is not None:
                    log("%s exited rc=%s - respawning in 3s" % (name, p.returncode))
                    time.sleep(3)
                log("starting %s: %s" % (name, " ".join(argv)))
                running[name] = subprocess.Popen(argv)
            time.sleep(5)
    except KeyboardInterrupt:
        log("shutdown - terminating children")
        for p in running.values():
            if p.poll() is None:
                p.terminate()
        for p in running.values():
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()


if __name__ == "__main__":
    main()
