"""v1.28 regression: dep/arr times + duration must render in v2 UI.

The original complaint was "页面无法显示航班班次的具体起飞时间" while the
data layer had 100% dep_time+arr_time coverage. These checks pin the
rendering logic in the three surfaces users actually look at."""
import re
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WEB = Path(__file__).resolve().parents[1] / "web"


def _src(name):
    return (WEB / "src" / "components" / name).read_text(encoding="utf-8")


def _dist_js():
    assets = (WEB / "dist" / "assets").glob("index-*.js")
    return max(assets, key=lambda p: p.stat().st_mtime).read_text(encoding="utf-8")


def test_calendar_chip_shows_dep_arr_pair():
    src = _src("CalendarView.jsx")
    assert 'd.dep_time + (d.arr_time ? "→" + d.arr_time' in src, \
        "calendar chip must render dep→arr, not dep alone"
    assert "起飞" in src  # fallback label when arr unknown


def test_bars_title_includes_times_and_duration():
    src = _src("CalendarView.jsx")
    m = re.search(r"const title = m.*?: ds.*?无数据\";", src, re.S)
    assert m, "bars title builder not found"
    body = m.group(0)
    assert "m.d.dep_time" in body and "m.d.arr_time" in body
    assert "m.d.duration_text" in body


def test_trend_tooltip_has_arr_and_duration():
    src = _src("TrendChart.jsx")
    assert "tip-time" in src, "tooltip must tag the dep→arr span"
    assert "tip-dur" in src, "tooltip must tag duration"
    assert re.search(r"\" · \" \+ hp\.d\.dep_time \+ \"起飞\"", src) or \
           "hp.d.dep_time + \"起飞\"" in src.replace("\n", " ")


def test_top5_row_shows_full_time_pair():
    src = _src("Top5.jsx")
    assert 'd.arr_time ? "→" + d.arr_time' in src
    assert "d.duration_text ? \" · \" + d.duration_text" in src


def test_dist_bundle_carries_new_logic():
    js = _dist_js()
    assert "tip-time" in js and "tip-dur" in js, \
        "dist bundle stale - run npm run build after src changes"


def test_snapshot_time_coverage_complete():
    import json
    snap = json.loads((WEB.parent / "data" / "snapshot.json").read_text(encoding="utf-8"))
    for r in snap.get("routes", []):
        with_dep = [d for d in r.get("deals", []) if d.get("dep_time")]
        both = [d for d in with_dep if d.get("arr_time")]
        assert with_dep, "%s has no timed deals" % r.get("id")
        # every timed deal should carry arr too (dep-only is the bug)
        assert len(both) == len(with_dep), (
            "%s: %d deals lack arr_time" % (r.get("id"), len(with_dep) - len(both)))


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("PASS %s" % fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL %s: %s" % (fn.__name__, e))
    sys.exit(1 if failed else 0)
