# -*- coding: utf-8 -*-
"""G1 gate (M2): source health unit tests. Run: python tests/test_health.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.health import SourceHealth, update_from_crawl


def _mk_crawl(path, steps):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"running": False, "current": None, "history": [
            {"run_id": "r1", "steps": steps}]}, f)


def test_score_window():
    h = SourceHealth(os.path.join(tempfile.mkdtemp(), "health.json"))
    for ok in (True, True, True, False, False):
        h.report("src", ok=ok)
    assert h.score("src") == 60  # 3/5 ok


def test_updated_at_persisted_to_disk():
    d = tempfile.mkdtemp()
    crawl = os.path.join(d, "crawl_status.json")
    _mk_crawl(crawl, [{"source": "qunar-calendar", "status": "ok", "error": ""}])
    update_from_crawl(d)
    with open(os.path.join(d, "health.json"), encoding="utf-8") as f:
        on_disk = json.load(f)
    assert on_disk["updated_at"]  # must be written, not lag one save behind


def test_mcp_degraded_lines_surfaces_diagnosis():
    import mcp_server
    d = tempfile.mkdtemp()
    _mk_crawl(os.path.join(d, "crawl_status.json"), [
        {"source": "qunar-calendar", "status": "error", "error": "HTTP 429 rate limited"},
        {"source": "qunar-calendar", "status": "error", "error": "HTTP 429 rate limited"}])
    h = update_from_crawl(d)
    lines = mcp_server._degraded_lines(h)
    assert len(lines) == 1 and lines[0].startswith("⚠ 数据源 qunar-calendar")
    assert "限频" in lines[0]  # diagnosis cause surfaced for agents


def test_inject_two_step_failure_degrades_in_one_run():
    d = tempfile.mkdtemp()
    _mk_crawl(os.path.join(d, "crawl_status.json"), [
        {"source": "qunar-calendar", "status": "error", "error": "HTTP 403 too many requests"},
        {"source": "qunar-calendar", "status": "error", "error": "HTTP 403 too many requests"},
        {"source": "12306-train", "status": "ok", "error": ""},
    ])
    h = update_from_crawl(d)
    snap = {s["source"]: s for s in h.snapshot()["sources"]}
    assert snap["qunar-calendar"]["degraded"] is True     # 2 fails in one run
    assert snap["12306-train"]["degraded"] is False
    assert snap["qunar-calendar"]["consecutive_fails"] == 1


def test_single_step_fail_needs_three_runs():
    d = tempfile.mkdtemp()
    crawl = os.path.join(d, "crawl_status.json")
    for _ in range(2):  # two failing runs: not yet degraded
        _mk_crawl(crawl, [{"source": "qunar-calendar", "status": "error", "error": "timeout"}])
        h = update_from_crawl(d)
    assert h.snapshot()["sources"][0]["degraded"] is False
    _mk_crawl(crawl, [{"source": "qunar-calendar", "status": "error", "error": "timeout"}])
    h = update_from_crawl(d)  # third consecutive failing run
    assert h.snapshot()["sources"][0]["degraded"] is True


def test_recovery_clears_degrade():
    d = tempfile.mkdtemp()
    crawl = os.path.join(d, "crawl_status.json")
    _mk_crawl(crawl, [{"source": "qunar-calendar", "status": "error", "error": "connection reset"},
                      {"source": "qunar-calendar", "status": "error", "error": "connection reset"}])
    h = update_from_crawl(d)
    assert h.snapshot()["sources"][0]["degraded"] is True
    _mk_crawl(crawl, [{"source": "qunar-calendar", "status": "ok", "error": ""}])
    h = update_from_crawl(d)
    assert h.snapshot()["sources"][0]["degraded"] is False


def test_diagnose_structure_and_classification():
    d = tempfile.mkdtemp()
    _mk_crawl(os.path.join(d, "crawl_status.json"), [
        {"source": "qunar-calendar", "status": "error", "error": "HTTP 429 Too Many Requests"}])
    h = update_from_crawl(d)
    rep = h.diagnose("qunar-calendar")
    need = {"source", "status", "score", "consecutive_fails",
            "last_error", "last_error_at", "candidates"}
    assert need.issubset(rep) and rep["status"] in ("ok", "failing", "degraded")
    causes = [c["cause"] for c in rep["candidates"]]
    assert "疑似反爬限频" in causes
    assert all(set(c) == {"cause", "action"} and c["action"] for c in rep["candidates"])


def run_all():
    fns = sorted((k, v) for k, v in list(globals().items())
                 if k.startswith("test_") and callable(v))
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print("PASS " + name)
        except Exception as e:
            failed += 1
            print("FAIL " + name + " " + repr(e))
    print("unit tests: {} pass / {} fail".format(len(fns) - failed, failed))
    return failed


if __name__ == "__main__":
    sys.exit(1 if run_all() else 0)
