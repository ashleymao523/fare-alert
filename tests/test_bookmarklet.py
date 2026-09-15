# -*- coding: utf-8 -*-
# v0.79 bookmarklet generator + city-pair point-fill resolution.
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.point_fill import build_bookmarklet


def test_bookmarklet_shape(tmpdir=None):
    code = build_bookmarklet("http://192.168.1.5:8765/")
    assert code.startswith("javascript:(function(){")
    assert "http://192.168.1.5:8765" in code
    assert "__FA_ORIGIN__" not in code
    for marker in ("/api/point-fill", "depCity", "goDate",
                   "from_city", "no-cors", "prompt"):
        assert marker in code, marker


def test_bookmarklet_origin_swap(tmpdir=None):
    a = build_bookmarklet("http://127.0.0.1:8765")
    b = build_bookmarklet("http://192.168.1.5:8765/")
    assert a != b
    assert "127.0.0.1:8765" in a and "192.168.1.5:8765" in b


def test_point_fill_city_pair(tmpdir=None):
    import webui
    snap = {"routes": [{"id": "r1", "from_city": "杭州", "to_city": "重庆",
                        "deals": []}]}
    old_snap, old_data = webui.SNAPSHOT_PATH, webui.DATA_DIR
    with tempfile.TemporaryDirectory() as td:
        webui.SNAPSHOT_PATH = os.path.join(td, "snap.json")
        webui.DATA_DIR = td
        with open(webui.SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False)
        c = webui.app.test_client()
        r = c.post("/api/point-fill", json={
            "from_city": "杭州", "to_city": "重庆",
            "rows": [{"date": "2026-09-20", "total": 480}]})
        assert r.status_code == 200 and r.get_json().get("ok")
        r2 = c.post("/api/point-fill", json={
            "from_city": "杭州", "to_city": "北京",
            "rows": [{"date": "2026-09-20", "total": 480}]})
        assert r2.status_code == 400
        r3 = c.get("/api/bookmarklet")
        j = r3.get_json()
        assert j.get("ok") and j["code"].startswith("javascript:")
        assert "/api/point-fill" in j["code"]
    webui.SNAPSHOT_PATH, webui.DATA_DIR = old_snap, old_data


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            with tempfile.TemporaryDirectory() as td:
                fn(td)
            print("PASS %s" % name)
            passed += 1
    print("OK %d tests" % passed)
