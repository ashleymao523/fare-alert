# -*- coding: utf-8 -*-
# v1.04: exact board hits upgrade booking-x rows (own flight beats pin).
import datetime
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.sched_board import apply_board_upgrade, board_lookup_x


ENT = {"dep": "13:10", "arr": "16:00", "from": "杭州", "to": "重庆"}


def test_upgrade_only_booking_x():
    d = SimpleNamespace(dep_src="airport-board", dep_time="07:00",
                        arr_src="airport-board", arr_time="09:30",
                        time_src="airport-board", borrow_dow="",
                        borrow_votes=0, borrow_unstable=False)
    assert apply_board_upgrade(d, ENT) is False
    assert d.dep_time == "07:00" and d.dep_src == "airport-board"
    plain = SimpleNamespace(dep_src="", dep_time="", time_src="",
                            arr_src="", arr_time="")
    assert apply_board_upgrade(plain, ENT) is False


def test_booking_x_upgraded_to_own_flight():
    d = SimpleNamespace(dep_src="booking-x", dep_time="16:55",
                        arr_src="booking-x", arr_time="19:40",
                        time_src="booking-x", borrow_dow="4",
                        borrow_votes=2, borrow_unstable=True)
    assert apply_board_upgrade(d, ENT) is True
    assert d.dep_time == "13:10" and d.arr_time == "16:00"
    assert d.dep_src == d.arr_src == d.time_src == "airport-board"
    assert d.borrow_dow == "" and d.borrow_votes == 0
    assert d.borrow_unstable is False


def test_no_dep_entry_never_upgrades():
    d = SimpleNamespace(dep_src="booking-x", dep_time="16:55",
                        arr_src="booking-x", arr_time="19:40",
                        time_src="booking-x", borrow_dow="",
                        borrow_votes=0, borrow_unstable=False)
    assert apply_board_upgrade(d, {"dep": "", "arr": "16:00"}) is False
    assert d.dep_time == "16:55"


def test_exact_vs_crossdow_policy_chain():
    # synthetic airport board: GS6582 flies HGH->CKG on Thu (dow 3 only)
    db = {"flights": {"GS6582": {"dows": {
        "3": {"dep": "13:10", "arr": "16:00",
              "from": "杭州", "to": "重庆"}}}}}
    # same-flight same-dow: exact hit -> caller applies the upgrade
    d1 = SimpleNamespace(dep_src="booking-x", dep_time="16:55",
                         arr_src="booking-x", arr_time="19:40",
                         time_src="booking-x", borrow_dow="",
                         borrow_votes=0, borrow_unstable=False)
    hit = board_lookup_x(db, "GS6582", "2026-09-17", "杭州", "重庆")
    assert hit is not None and hit[1] is True
    assert apply_board_upgrade(d1, hit[0]) is True
    assert d1.dep_src == "airport-board"
    # wrong weekday (Friday): cross-dow borrow only -> caller policy
    # (exact=False) must NOT call the upgrade; pin stays in place
    hit2 = board_lookup_x(db, "GS6582", "2026-09-18", "杭州", "重庆")
    assert hit2 is not None and hit2[1] is False
    d2 = SimpleNamespace(dep_src="booking-x", dep_time="16:55",
                         arr_src="booking-x", arr_time="19:40",
                         time_src="booking-x", borrow_dow="",
                         borrow_votes=0, borrow_unstable=False)
    exact2 = hit2[1]
    upgraded = exact2 and apply_board_upgrade(d2, hit2[0])
    assert not upgraded and d2.dep_src == "booking-x"


def test_no_pingpong_with_booking_attach():
    # next cycle booking_attach_times must skip rows already exact:
    # its EXACT_SOURCES gate has to contain airport-board
    from core.booking_fill import EXACT_SOURCES
    assert "airport-board" in EXACT_SOURCES


if __name__ == "__main__":
    test_upgrade_only_booking_x()
    test_booking_x_upgraded_to_own_flight()
    test_no_dep_entry_never_upgrades()
    test_exact_vs_crossdow_policy_chain()
    test_no_pingpong_with_booking_attach()
    print("test_v104 OK")
