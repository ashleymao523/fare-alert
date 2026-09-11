# -*- coding: utf-8 -*-
"""Dump rendered DOM of the three main tabs via headless Edge.

Replaces tools/dump_dom.cmd: the cmd orchestrator relied on ping sleeps
between tabs, so a killed parent left tabs 2/3 unwritten. Here each Edge
run is waited on synchronously and the merge happens after all three
finish, so data/ui_dom.html is never observed half-written.
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TABS = [("p1", "crawl"), ("p2", "reverse"), ("p3", "weekly"),
        ("p4", "sources"), ("p5", "push")]


def main():
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.exists(EDGE):
        print("FAIL msedge not found at " + EDGE)
        return 1
    parts = []
    for prof, tab in TABS:
        udd = os.path.join(cwd, "data", "edge_prof_" + prof)
        url = "http://127.0.0.1:8765/?v=25#" + tab
        cmd = [EDGE, "--headless", "--disable-gpu", "--no-first-run",
               "--user-data-dir=" + udd, "--virtual-time-budget=30000",
               "--dump-dom", url]
        # no cwd=: Edge (Store build) fails with WinError 267 on a CJK cwd
        out = b""
        for attempt in (1, 2):  # headless Edge crashes (rc 21) when the
            # previous run has not released the profile yet -> retry once
            p = subprocess.run(cmd, capture_output=True, timeout=120)
            out = p.stdout
            if out:
                break
            print(tab + " attempt " + str(attempt) + " empty (rc " +
                  str(p.returncode) + "), retry in 5s", flush=True)
            time.sleep(5)
        parts.append(out.decode("utf-8", "replace"))
        print(tab + " bytes " + str(len(out)), flush=True)
        time.sleep(3)
    out = os.path.join(cwd, "data", "ui_dom.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print("MERGED into " + out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
