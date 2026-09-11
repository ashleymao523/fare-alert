# -*- coding: utf-8 -*-
"""G1 gate: core unit tests. Run: python tests/test_core.py (or tools/acceptance.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.alerts import evaluate, tax_amount, total_price
from core.flights import estimate_arrival_time
from core.models import FlightDeal, TrainFare
from main import (NON_REAL_SOURCES, _attach_alt_times, _fill_reference_deals,
                  _flight_dict)

TAX = {"airport_fee": 70, "fuel_surcharge": 50}  # 120, current default


def _alt_db(*rows):
    flights = {}
    for no, dow, dep, frm, to in rows:
        flights.setdefault(no, {"dows": {}})["dows"][str(dow)] = {
            "dep": dep, "arr": "", "from": frm, "to": to}
    return {"updated": 1, "flights": flights}


def test_tax_total():
    assert total_price(400, TAX) == 520
    assert tax_amount(TAX) == 120
    inc = {"calendar_price_includes_tax": True, "airport_fee": 70}
    assert total_price(400, inc) == 400  # calendar already tax-included


def test_student_est():
    t = TrainFare(pair="p", train_code="D2262", from_station="a", to_station="b",
                  dep_time="08:08", arr_time="19:31", duration_text="11:23",
                  seats={"二等座": 513.5})
    est = t.student_second_class_est
    assert est and 385.0 < est < 385.3  # 513.5 * 0.75


def test_estimate_arrival_time():
    # HGH->CKG great circle ~2h30m incl. taxi, consistent w/ duration est
    assert estimate_arrival_time("07:55", "HGH", "CKG") == "10:25"
    assert estimate_arrival_time("23:00", "HGH", "CKG") == "01:30"  # +1d
    assert estimate_arrival_time("07:55", "HGH", "CTU",
                                 connecting=True) == "13:15"
    assert estimate_arrival_time("07:55", "", "CKG") == ""  # unknown coord
    assert estimate_arrival_time("bad", "HGH", "CKG") == ""  # bad dep time


def test_estimate_arrival_time_prior():
    # v0.25: real reverse-leg minutes beat the great-circle guess
    assert estimate_arrival_time("08:00", "HGH", "CKG",
                                 prior_minutes=155) == "10:35"
    assert estimate_arrival_time("23:00", "HGH", "",
                                 prior_minutes=155) == "01:35"  # +1d
    assert estimate_arrival_time("08:00", "", "",
                                 prior_minutes=100) == "09:40"  # no coords needed
    # connecting keeps the great-circle + layover model: the prior covers
    # one single leg only and cannot be mapped to a multi-leg itinerary
    assert estimate_arrival_time("08:00", "HGH", "BKK",
                                 connecting=True,
                                 prior_minutes=240) == "14:50"


def test_flight_dict_serializes_arr_est():
    d = FlightDeal(date="2026-09-10", bare_price=300, flight_no="GJ8888",
                   dep_time="07:55", arr_est="10:25")
    route = {"from_city": "杭州", "to_city": "重庆", "threshold_total": 500}
    out = _flight_dict(route, d, {"tax": TAX}, set())
    assert out["arr_est"] == "10:25" and out["arr_time"] == ""


def test_interp_two_side():
    deals = [FlightDeal("2026-09-01", 100, "MU5100", dep_time="08:00",
                        arr_time="10:30", duration_text="2:30"),
             FlightDeal("2026-09-05", 204, "CA1858")]
    by = {d.date: d for d in _fill_reference_deals(
        deals, "2026-09-01", "2026-09-08", "A", "B")}
    d3 = by["2026-09-03"]
    assert d3.source == "interp" and d3.bare_price == 150
    assert d3.flight_no == "MU5100" and d3.dep_time == "08:00"  # nearer neighbor


def test_interp_single_side_fallback():
    deals = [FlightDeal("2026-09-01", 100, "MU5100")]
    by = {d.date: d for d in _fill_reference_deals(
        deals, "2026-09-01", "2026-09-03", "A", "B")}
    d3 = by["2026-09-03"]
    assert d3.source == "nearby-ref" and d3.ref_offset == 2


def test_estimated_sources_isolated():
    deals = [FlightDeal("2026-09-02", 100, "MU5100"),
             FlightDeal("2026-09-03", 90, "XX0000", source="interp"),
             FlightDeal("2026-09-04", 80, "YY0000", source="nearby-ref")]
    real = [d for d in deals if d.source not in NON_REAL_SOURCES]
    assert len(real) == 1 and real[0].date == "2026-09-02"


def test_evaluate_dedup_and_realert():
    route = {"id": "t", "threshold_total": 530}
    d = FlightDeal("2026-09-02", 400, "MU5100")
    state = {}
    t0 = 1.75e9  # realistic unix ts; cooldown compares against epoch 0
    a1, below1 = evaluate(route, [d], state, {"tax": TAX, "alert": {}}, t0)
    assert len(a1) == 1 and len(below1) == 1
    a2, _ = evaluate(route, [d], state, {"tax": TAX, "alert": {}}, t0 + 1000)
    assert a2 == []  # same price inside 6h cooldown: silent
    d2 = FlightDeal("2026-09-02", 380, "MU5100")
    a3, _ = evaluate(route, [d2], state, {"tax": TAX, "alert": {}}, t0 + 1e5)
    assert len(a3) == 1  # dropped >= 5 and cooldown passed: re-alert


def test_attach_alt_times_fills_gap_deals():
    # v0.26.1: nearby-ref deals appended after enrich get board reference
    # departures; a numbered deal with a real time stays untouched
    db = _alt_db(("JD419", 4, "08:35", "杭州", "曼谷素万那普机场"),
                 ("FD497", 4, "18:10", "杭州", "曼谷素万那普机场"))
    deals = [
        FlightDeal(date="2026-09-25", bare_price=900, flight_no="",
                   source="nearby-ref", ref_offset=2),
        FlightDeal(date="2026-09-25", bare_price=800, flight_no="JD419",
                   dep_time="08:35", source="qunar-intl"),
    ]
    out = _attach_alt_times(deals, "曼谷", db)
    got = [(a['no'], a['dep'], a['exact']) for a in out[0].alt_times]
    assert got == [('JD419', '08:35', True), ('FD497', '18:10', True)]
    assert out[1].alt_times == []


def test_attach_alt_times_idempotent_and_empty_city():
    db = _alt_db(("JD419", 4, "08:35", "杭州", "曼谷"))
    d = FlightDeal(date="2026-09-25", bare_price=900, flight_no="",
                   source="nearby-ref")
    d.alt_times = [{"no": "XX", "dep": "00:00", "exact": False}]
    _attach_alt_times([d], "曼谷", db)
    assert d.alt_times == [{"no": "XX", "dep": "00:00", "exact": False}]
    e = FlightDeal(date="2026-09-25", bare_price=900, flight_no="",
                   source="nearby-ref")
    _attach_alt_times([e], "", db)
    assert e.alt_times == []


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
