# -*- coding: utf-8 -*-
"""G1 gate (M1): intent parsing unit tests. Run: python tests/test_intent.py"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.intent import parse_intent, window_from_date

TODAY = dt.date(2026, 9, 10)  # frozen for reproducibility


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


def test_basic():
    r = parse_intent("五一杭州飞成都800以内", TODAY)
    assert r["from_city"] == "杭州" and r["to_city"] == "成都"
    assert r["threshold_total"] == 800
    assert r["date_from"] == "2027-05-01"  # 2026-05-01 passed -> next year
    assert r["route_id"] == "hangzhou-chengdu" and r["ok"]


def test_direction_word():
    r = parse_intent("帮我盯北京到上海 600 元以下", TODAY)
    assert r["from_city"] == "北京" and r["to_city"] == "上海"
    assert r["threshold_total"] == 600


def test_window_days():
    r = parse_intent("杭州飞重庆 30 天内低于 500", TODAY)
    assert r["window_days"] == 30 and r["threshold_total"] == 500


def test_holiday_qingming_approx():
    r = parse_intent("国庆从上海去成都 预算1000", TODAY)
    assert r["from_city"] == "上海" and r["to_city"] == "成都"
    assert r["date_from"] == "2026-10-01" and r["threshold_total"] == 1000


def test_dash_pair():
    r = parse_intent("深圳-西安 750以内", TODAY)
    assert r["from_city"] == "深圳" and r["to_city"] == "西安"
    assert r["threshold_total"] == 750


def test_roundtrip():
    r = parse_intent("杭州往返成都 800以内", TODAY)
    assert r["trip_type"] == "roundtrip"


def test_explicit_date():
    r = parse_intent("3月15号杭州飞北京500以内", TODAY)
    assert r["date_from"] == "2027-03-15" and r["threshold_total"] == 500


def test_empty():
    r = parse_intent("", TODAY)
    assert not r["ok"] and r["ambiguous"]


def test_no_threshold_ok():
    r = parse_intent("杭州飞成都", TODAY)
    assert r["ok"] and r["threshold_total"] is None
    assert any("阈值" in a for a in r["ambiguous"])


def test_spring_festival_floating():
    r = parse_intent("春节杭州飞广州", TODAY)
    assert r["date_from"] == "2027-02-17"  # 2026-02-17 passed
    assert any("春节" in a for a in r["ambiguous"])


def test_direction_words_regression():
    # E2E found: direction suffix used to flip this pair
    r = parse_intent("去西安从杭州出发600以内", TODAY)
    assert r["from_city"] == "杭州" and r["to_city"] == "西安"


def test_window_from_date_no_offbyone():
    r = parse_intent("国庆杭州飞西安600以内", TODAY)
    assert window_from_date(r, TODAY) == 80  # 21 lead + 60 - 1
    assert parse_intent("杭州飞西安", TODAY)["window_days"] == 60  # no date: unchanged


if __name__ == "__main__":
    sys.exit(1 if run_all() else 0)
