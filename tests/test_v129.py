# -*- coding: utf-8 -*-
"""v1.29: CDP cabin manual trigger + agent ledger registration.

The patrol hook only fires on throttle or every 4th round (~2h at
30min cadence); a human watching grey gap dates needs a button.
These checks pin the endpoint surface and the ledger entry."""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_SRC = open(os.path.join(ROOT, "webui.py"), encoding="utf-8").read()


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (" " + str(extra) if extra else ""))
    return bool(cond)


def main():
    ok = True

    # 1. endpoint exists, forces past cadence, keeps daily cap
    ok &= check("endpoint route present",
                '@app.post("/api/tasks/cdp-cabin/run")' in WEBUI_SRC)
    m = re.search(
        r"def api_tasks_cdp_cabin_run.*?(?=\n@app\.)", WEBUI_SRC, re.S)
    body = m.group(0) if m else ""
    ok &= check("forces throttle_hits=1 past cadence gate",
                "throttle_hits=1" in body, body[:80])
    ok &= check("reuses patrol_fill (cap-bound inside)",
                "from core.cdp_cabin import patrol_fill" in body)
    ok &= check("errors become 500 not crash",
                '"error": str(e)' in body)

    # 2. ledger registers the agent with manual trigger
    from core.agent_tasks import build_ledger
    tmp = tempfile.mkdtemp()
    led = {"rounds": 7, "days": {}}
    with open(os.path.join(tmp, "cdp_cabin_ledger.json"), "w",
              encoding="utf-8") as f:
        json.dump(led, f)
    cfg = {"cabin_watch": {"refresh_minutes": 30,
                           "cdp_capture_daily_cap": 12}}
    doc = build_ledger(tmp, cfg)
    agents = {a["id"]: a for a in doc["agents"]}
    a = agents.get("cdp-cabin")
    ok &= check("ledger has cdp-cabin agent", a is not None)
    if a:
        ok &= check("manual trigger wired",
                    a["manual_trigger"] == "/api/tasks/cdp-cabin/run")
        ok &= check("cadence = 2x patrol = 60min (v1.30 speedup)",
                    a["cadence_minutes"] == 60, a["cadence_minutes"])
        ok &= check("detail shows round + cap",
                    "7" in a["detail"] and "0/12" in a["detail"],
                    a["detail"])
        ok &= check("last_run from ledger mtime",
                    a["last_run"] is not None)

    # 3. daily-cap respects config override
    cfg2 = {"cabin_watch": {"refresh_minutes": 30,
                            "cdp_capture_daily_cap": 4}}
    a2 = {x["id"]: x for x in build_ledger(tmp, cfg2)["agents"]}["cdp-cabin"]
    ok &= check("cap override 4 honoured", "0/4" in a2["detail"],
                a2["detail"])

    print("v1.29 checks: %s" % (
        "all pass" if ok else "FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
