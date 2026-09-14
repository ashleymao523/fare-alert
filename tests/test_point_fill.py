# -*- coding: utf-8 -*-
# v0.76 point-fill cache: put/load roundtrip, TTL, real-row guard,
# snapshot hot-patch and gap_dates window logic.
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import point_fill as pf
from core.models import FlightDeal


def mk_deal(date, price, source="qunar-calendar", **kw):
    return FlightDeal(date=date, bare_price=price,
                      flight_no=kw.get("flight_no", "3U8888"),
                      source=source, **{k: v for k, v in kw.items()
                                        if k != "flight_no"})


def test_put_and_load_roundtrip(tmpdir):
    rows = [
        {"date": "2026-09-20", "total": 640, "flight_no": "GJ8881",
         "dep_time": "07:35", "arr_time": "10:20"},
        {"date": "bad-date", "total": 500},
        {"date": "2026-09-21", "total": "abc"},
        {"date": "2026-09-22", "total": 0},
        "not-a-dict",
    ]
    cache, n = pf.put_rows(tmpdir, "HQ-CQ", rows, tax=120)
    assert n == 1
    again = pf.load_cache(tmpdir)
    e = again["HQ-CQ"]["2026-09-20"]
    assert e["bare"] == 520.0 and e["total"] == 640.0
    assert e["flight_no"] == "GJ8881"
    assert e["dep_time"] == "07:35" and e["arr_time"] == "10:20"
    assert "bad-date" not in again["HQ-CQ"]
    assert "2026-09-21" not in again["HQ-CQ"]
    assert "2026-09-22" not in again["HQ-CQ"]


def test_fresh_entries_ttl_and_garbage(tmpdir=None):
    now = time.time()
    cache = {"HQ-CQ": {
        "2026-09-20": {"bare": 500, "total": 620, "ts": now - 100},
        "2026-09-21": {"bare": 400, "total": 520, "ts": now - pf.POINT_TTL - 1},
        "junk": {"bare": 1, "total": 2, "ts": now},
        "2026-09-23": {"bare": 0, "total": 0, "ts": now},
        "nope": 42,
    }}
    fresh = pf.fresh_entries(cache, "HQ-CQ", now=now)
    assert list(fresh) == ["2026-09-20"]
    assert pf.fresh_entries({}, "HQ-CQ") == {}


def test_merge_replaces_ref_only_rows(tmpdir=None):
    now = time.time()
    cache = {"HQ-CQ": {
        "2026-09-19": {"bare": 480.0, "total": 600.0, "flight_no": "GJ8001",
                       "dep_time": "08:00", "arr_time": "10:45", "ts": now},
        "2026-09-20": {"bare": 520.0, "total": 640.0, "flight_no": "GJ8002",
                       "dep_time": "13:10", "arr_time": "15:55", "ts": now},
    }}
    deals = [
        mk_deal("2026-09-18", 610.0),                       # real row
        mk_deal("2026-09-19", 700.0, source="nearby-ref"),  # ref row -> replaced
        mk_deal("2026-09-20", 800.0, source="interp"),      # ref row -> replaced
        mk_deal("2026-09-21", 750.0, source="interp"),      # no cache entry
    ]
    out, n = pf.merge_point_fill(deals, cache, "HQ-CQ", now=now)
    assert n == 2
    by = {d.date: d for d in out}
    assert by["2026-09-18"].source == "qunar-calendar"      # real wins
    assert by["2026-09-19"].source == pf.POINT_SOURCE
    assert by["2026-09-19"].bare_price == 480.0
    assert by["2026-09-19"].flight_no == "GJ8001"
    assert by["2026-09-19"].dep_time == "08:00"
    assert by["2026-09-19"].arr_time == "10:45"
    assert by["2026-09-21"].source == "interp"              # untouched
    assert [d.date for d in out if d.source == pf.POINT_SOURCE] == \
        ["2026-09-19", "2026-09-20"]
    prices = [d.bare_price for d in out]
    assert prices == sorted(prices)


def test_merge_skips_stale_and_keeps_real_rows(tmpdir=None):
    now = time.time()
    stale = {"HQ-CQ": {"2026-09-19": {"bare": 300.0, "total": 420.0,
                                      "ts": now - pf.POINT_TTL - 5}}}
    deals = [mk_deal("2026-09-19", 700.0, source="interp")]
    out, n = pf.merge_point_fill(deals, stale, "HQ-CQ", now=now)
    assert n == 0 and out[0].source == "interp"

    fresh = {"HQ-CQ": {"2026-09-19": {"bare": 300.0, "total": 420.0,
                                      "ts": now}}}
    real = [mk_deal("2026-09-19", 700.0)]  # qunar real row: never touched
    out, n = pf.merge_point_fill(real, fresh, "HQ-CQ", now=now)
    assert n == 0 and out[0].source == "qunar-calendar"
    assert out[0].bare_price == 700.0


def test_patch_snapshot_deals_dict_rows(tmpdir=None):
    now = time.time()
    cache = {"HQ-CQ": {"2026-09-19": {
        "bare": 480.0, "total": 600.0, "flight_no": "GJ8001",
        "dep_time": "08:00", "arr_time": "10:45", "ts": now}}}
    deals = [
        {"date": "2026-09-18", "bare_price": 610.0, "source": "qunar-calendar"},
        {"date": "2026-09-19", "bare_price": 700.0, "source": "nearby-ref",
         "ref_offset": 2, "total_price": 820.0},
        {"date": "2026-09-20", "bare_price": 800.0, "source": "interp",
         "ref_offset": 0},
    ]
    n = pf.patch_snapshot_deals(deals, cache, "HQ-CQ", now=now)
    assert n == 1
    assert deals[0]["source"] == "qunar-calendar"
    assert deals[1]["source"] == pf.POINT_SOURCE
    assert deals[1]["bare_price"] == 480.0
    assert deals[1]["total_price"] == 600.0  # synced with stored total
    assert deals[1]["ref_offset"] == 0
    assert deals[1]["flight_no"] == "GJ8001"
    assert deals[1]["dep_time"] == "08:00"
    assert deals[2]["source"] == "interp"  # no cache entry: untouched
    assert pf.patch_snapshot_deals(None, cache, "HQ-CQ") == 0


def test_gap_dates_window_logic(tmpdir=None):
    deals = [{"date": "2026-09-01", "source": "qunar-calendar"},
             {"date": "2026-09-02", "source": "interp"},
             {"date": "2026-09-03", "source": "nearby-ref"},
             {"date": "2026-09-04", "source": "point-fill"}]
    gaps = pf.gap_dates(deals, ("2026-09-01", "2026-09-05"))
    assert gaps == ["2026-09-02", "2026-09-03", "2026-09-05"]
    assert pf.gap_dates(deals, ("oops", "2026-09-05")) == []
    assert pf.gap_dates(deals, ("2026-09-10", "2026-09-08")) == []
    assert pf.gap_dates(None, ("2026-09-01", "2026-09-03")) == \
        ["2026-09-01", "2026-09-02", "2026-09-03"]


def test_put_rows_overwrites_and_trims(tmpdir=None):
    now = time.time()
    pf.put_rows(tmpdir, "HQ-CQ",
                [{"date": "2026-09-19", "total": 900}], tax=120, now=now)
    pf.put_rows(tmpdir, "HQ-CQ",
                [{"date": "2026-09-19", "total": 640}], tax=120, now=now)
    e = pf.load_cache(tmpdir)["HQ-CQ"]["2026-09-19"]
    assert e["total"] == 640.0 and e["bare"] == 520.0


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            with tempfile.TemporaryDirectory() as td:
                fn(td)
            print("PASS %s" % name)
            passed += 1
    print("OK %d tests" % passed)
