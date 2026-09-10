# -*- coding: utf-8 -*-
"""Executable acceptance gates G0-G6 (see docs/验收规范.md).

Usage: python tools/acceptance.py   (run from repo root or anywhere)
Exit code 0 = all gates PASS/SKIP, 1 = at least one FAIL.
"""
import glob
import json
import os
import py_compile
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NON_REAL = ("nearby-ref", "interp")
results = []


def rec(gate, name, ok, note=""):
    results.append((gate, name, "PASS" if ok else "FAIL", note))


def skip(gate, name, note):
    results.append((gate, name, "SKIP", note))


# ---------- G0 static ----------
def gate_g0():
    targets = ["main.py", "webui.py"] + glob.glob("core/*.py") \
        + glob.glob("tools/*.py") + glob.glob("tests/*.py")
    bad = []
    for p in targets:
        try:
            py_compile.compile(p, doraise=True)
        except Exception as e:
            bad.append(p + ": " + str(e)[:60])
    rec("G0", "py compile x%d" % len(targets), not bad, "; ".join(bad))
    try:
        r = subprocess.run(["node", "--check", "webui/static/app.js"],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        rec("G0", "node --check app.js", r.returncode == 0,
            (r.stderr or "")[:100])
    except FileNotFoundError:
        skip("G0", "node --check app.js", "node 未安装")


# ---------- G1 unit ----------
def gate_g1():
    r = subprocess.run([sys.executable, "tests/test_core.py"],
                       capture_output=True, text=True, timeout=120,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    rec("G1", "tests/test_core.py", r.returncode == 0,
        "; ".join(fails)[:160] or out.strip().splitlines()[-1] if out.strip() else "")



# ---------- G3 UI DOM assertions (dump first, see AGENTS.md) ----------
def gate_g3():
    dom = "data/ui_dom.html"
    if not os.path.exists(dom):
        skip("G3", "ui_check", "无 DOM 快照，先跑 tools/dump_dom.cmd")
        return
    r = subprocess.run([sys.executable, "tools/ui_check.py"],
                       capture_output=True, text=True, timeout=120,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    note = "; ".join(fails)[:160]
    snap = "data/snapshot.json"
    if os.path.exists(snap) and os.path.getmtime(dom) < os.path.getmtime(snap):
        note = (note + " | DOM 早于 snapshot，建议重跑 dump_dom").strip(" |")
    rec("G3", "ui_check DOM", r.returncode == 0 and not fails, note)


# ---------- G2 API contract (webui must be running) ----------
def gate_g2():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/snapshot",
                                    timeout=5) as resp:
            snap = json.loads(resp.read().decode("utf-8")).get("snapshot")
    except Exception as e:
        skip("G2", "/api/snapshot", "webui 未运行(" + str(e)[:40] + ")")
        return
    ok = isinstance(snap, dict) and isinstance(snap.get("routes"), list) \
        and len(snap["routes"]) > 0
    note = ""
    if ok:
        d = snap["routes"][0].get("deals") or []
        need = {"date", "bare_price", "total_price", "source", "url"}
        ok = bool(d) and need.issubset(set(d[0].keys()))
        note = "routes=%d deals[0]=%d" % (len(snap["routes"]), len(d))
    rec("G2", "/api/snapshot contract", ok, note)


# ---------- G4 behaviour: KPI consistency on live data ----------
def gate_g4():
    path = "data/snapshot.json"
    if not os.path.exists(path):
        skip("G4", "KPI vs real-min", "无 snapshot，先跑一次抓取")
        return
    snap = json.load(open(path, encoding="utf-8"))
    bad = []
    checked = 0
    for r in snap.get("routes", []):
        if r.get("trip_type") == "roundtrip" or r.get("cheapest_total") is None:
            continue
        real = [d for d in (r.get("deals") or []) if d.get("source") not in NON_REAL]
        if not real:
            bad.append(r.get("id") + ": 无真实价但有KPI")
            continue
        checked += 1
        mn = min(d["total_price"] for d in real)
        if abs(mn - r["cheapest_total"]) > 0.51:
            bad.append("%s: kpi=%s real-min=%s" %
                       (r.get("id"), r.get("cheapest_total"), mn))
    rec("G4", "cheapest_total==real-min x%d" % checked, not bad,
        "; ".join(bad)[:160])


# ---------- G5 compliance ----------
def gate_g5():
    r = subprocess.run(["git", "ls-files", "config.json"],
                       capture_output=True, text=True, timeout=15,
                       encoding="utf-8", errors="replace")
    rec("G5", "config.json untracked", r.stdout.strip() == "", r.stdout.strip())
    gi = open(".gitignore", encoding="utf-8").read()
    rec("G5", "gitignore covers secrets",
        ("config.json" in gi) and ("data/" in gi), "")
    try:
        ex = json.load(open("config.example.json", encoding="utf-8"))
        iv = ex.get("schedule", {}).get("interval_minutes", 0)
        rec("G5", "default interval>=30min", iv >= 30, "interval=%s" % iv)
    except Exception as e:
        rec("G5", "config.example.json", False, str(e)[:80])


# ---------- G6 docs ----------
def gate_g6():
    need = ["README.md", "使用指南.md", "AGENTS.md",
            "docs/验收规范.md", "docs/迭代路线图.md"]
    miss = [p for p in need if not os.path.exists(p)]
    rec("G6", "docs x%d" % len(need), not miss, "缺: " + ",".join(miss))
    guide = open("使用指南.md", encoding="utf-8").read(400)
    html = open("webui/templates/index.html", encoding="utf-8").read()
    ver_html = "v0.11" in html
    rec("G6", "version badge sync", ver_html and "v0.11" in guide,
        "html v0.11=%s guide v0.11=%s" % (ver_html, "v0.11" in guide))


def main():
    gate_g0()
    gate_g1()
    gate_g3()
    gate_g2()
    gate_g4()
    gate_g5()
    gate_g6()
    lines = []
    fails = 0
    for gate, name, st, note in results:
        if st == "FAIL":
            fails += 1
        lines.append("%-3s %-4s %-36s %s" % (gate, st, name, note))
    report = "\n".join(lines) \
        + "\nverdict: %d FAIL / %d checks\n" % (fails, len(results))
    print(report)
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/acceptance_report.txt", "w", encoding="utf-8") as f:
            f.write(report + "\n")
    except Exception:
        pass
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
