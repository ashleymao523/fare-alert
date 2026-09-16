# -*- coding: utf-8 -*-
# v1.02: point-gaps auto_fill contract + weekly sched-dow line.
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.weekly import _sched_dow_line


DEALS8 = [{"date": "2026-09-%02d" % (17 + i), "total_price": 400 + i,
           "source": "interp"} for i in range(8)]


def _client_with(tmp, ama_cfg):
    import webui
    snap = {"routes": [{"id": "r1", "from_city": "杭州", "to_city": "重庆",
                        "deals": DEALS8, "window": ["2026-09-17", "2026-09-24"]}],
            "generated_at": "2026-09-16T09:00:00"}
    with open(os.path.join(tmp, "snap.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)
    cfg = {"refresh_minutes": 30,
           "sources": {"amadeus": ama_cfg} if ama_cfg else {}}
    with open(os.path.join(tmp, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)
    old = (webui.SNAPSHOT_PATH, webui.DATA_DIR, webui.CONFIG_PATH)
    webui.SNAPSHOT_PATH = os.path.join(tmp, "snap.json")
    webui.DATA_DIR = tmp
    webui.CONFIG_PATH = os.path.join(tmp, "config.json")
    return webui.app.test_client(), old, webui


def test_auto_fill_block_keyless():
    with tempfile.TemporaryDirectory() as td:
        c, old, webui = _client_with(td, None)
        try:
            r = c.get("/api/point-gaps")
            assert r.status_code == 200
            j = r.get_json()
            af = j.get("auto_fill") or {}
            assert af.get("amadeus_ready") is False
            assert af.get("per_round") == 6
            assert af.get("interval_min") == 30
            assert af.get("eta_rounds") == 2
            assert str(af.get("register_url")).startswith(
                "https://developer.amadeus.com")
            assert len((j.get("routes") or [])[0]["gaps"]) == 8
        finally:
            webui.SNAPSHOT_PATH, webui.DATA_DIR, webui.CONFIG_PATH = old


def test_auto_fill_block_armed():
    with tempfile.TemporaryDirectory() as td:
        c, old, webui = _client_with(
            td, {"env": "test", "client_id": "cid", "client_secret": "sec"})
        try:
            r = c.get("/api/point-gaps")
            af = r.get_json().get("auto_fill") or {}
            assert af.get("amadeus_ready") is True
            assert af.get("eta_rounds") == 2
        finally:
            webui.SNAPSHOT_PATH, webui.DATA_DIR, webui.CONFIG_PATH = old


def test_sched_dow_line_states():
    assert _sched_dow_line(None) == ""
    with tempfile.TemporaryDirectory() as td:
        line = _sched_dow_line(td)  # empty db -> 0/7, honest fresh state
        assert "0/7" in line


def test_sched_dow_line_sunday_hole():
    import datetime
    with tempfile.TemporaryDirectory() as td:
        full = {"flights": {"CA1": {"dows": {
            str(i): {"dep": "07:00"} for i in range(7)}}}}
        with open(os.path.join(td, "flight_sched_db.json"), "w",
                  encoding="utf-8") as f:
            json.dump(full, f, ensure_ascii=False)
        assert _sched_dow_line(td) == ""
        full["flights"]["CA1"]["dows"].pop("6")
        with open(os.path.join(td, "flight_sched_db.json"), "w",
                  encoding="utf-8") as f:
            json.dump(full, f, ensure_ascii=False)
        line = _sched_dow_line(td)
        assert "6/7" in line and "周日" in line and "自动补齐" in line
        d = datetime.date.today()
        while d.weekday() != 6:
            d += datetime.timedelta(days=1)
        assert d.strftime("%m/%d") in line


if __name__ == "__main__":
    test_auto_fill_block_keyless()
    test_auto_fill_block_armed()
    test_sched_dow_line_states()
    test_sched_dow_line_sunday_hole()
    print("test_v102 OK")
