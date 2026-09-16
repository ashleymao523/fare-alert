# -*- coding: utf-8 -*-
# v1.03: time_kind classification + time_coverage ref_* counters.
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.flights import time_kind, time_coverage


def test_time_kind_mapping():
    # five mappings: booking/point-fill -> exact, booking-x -> borrow,
    # alt-ref -> alt, empty/None/unknown -> noref
    assert time_kind("booking") == "exact"
    assert time_kind("point-fill") == "exact"
    assert time_kind("amadeus") == "exact"
    assert time_kind("airport-board") == "exact"
    assert time_kind("booking-x") == "borrow"
    assert time_kind("airport-board-x") == "borrow"
    assert time_kind("alt-ref") == "alt"
    assert time_kind("") == "noref"
    assert time_kind(None) == "noref"
    assert time_kind("mystery") == "noref"


def test_ref_rows_counted_separately():
    # booking-ref PRICE row carrying a booking dep_time: feeds ref_*
    # counters only, never the real-price denominator (the v1.03 fix
    # for the dep_exact=0 illusion on 144/240 snapshot rows)
    d = SimpleNamespace(source="booking-ref", dep_src="booking",
                        dep_time="08:30", arr_src="booking",
                        arr_time="11:05", arr_est="", date="2026-09-18")
    cov = time_coverage([d], today=__import__("datetime").date(2026, 9, 16))
    assert cov["ref_total"] == 1
    assert cov["ref_dep_exact"] == 1
    assert cov["ref_dep_borrow"] == 0
    assert cov["ref_dep_missing"] == 0
    assert cov["total"] == 0
    assert cov["dep_exact"] == 0


def test_real_point_fill_row_is_exact():
    d = SimpleNamespace(source="qunar", dep_src="point-fill",
                        dep_time="07:55", arr_src="point-fill",
                        arr_time="10:40", arr_est="", date="2026-09-19")
    cov = time_coverage([d], today=__import__("datetime").date(2026, 9, 16))
    assert cov["total"] == 1
    assert cov["dep_exact"] == 1
    assert cov["dep_borrow"] == 0
    assert cov["arr_exact"] == 1
    assert cov["ref_total"] == 0


def test_real_booking_x_row_is_borrow():
    d = SimpleNamespace(source="qunar", dep_src="booking-x",
                        dep_time="09:10", arr_src="booking-x",
                        arr_time="12:00", arr_est="", date="2026-09-19")
    cov = time_coverage([d], today=__import__("datetime").date(2026, 9, 16),
                        dows={"0": 1, "1": 1, "2": 1, "3": 1, "4": 1,
                              "5": 1, "6": 1})
    assert cov["total"] == 1
    assert cov["dep_borrow"] == 1
    assert cov["dep_exact"] == 0
    assert cov["arr_borrow"] == 1


if __name__ == "__main__":
    test_time_kind_mapping()
    test_ref_rows_counted_separately()
    test_real_point_fill_row_is_exact()
    test_real_booking_x_row_is_borrow()
    print("test_v103 OK")
