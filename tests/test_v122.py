# -*- coding: utf-8 -*-
"""v1.22 acceptance: ctrip CDP board module (rebuilt 2026-09-17)."""
import datetime as _dt
import json
import os
import tempfile
import time
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import cdp_board as cb
from core.sched_board import _atomic_write

HEADER = ("吉祥航空 HO1254 | 航班计划 | 航班动态数据来源于飞友，"
          "请以实际为准")
LEFT = ("北京大兴 | 上海浦东 | T2 | 预计起飞 10/25 | 预计到达 10/25"
        " | 21:25 | 23:40 | 计划时间 21:25 | 计划时间 23:40"
        " | 请以计划时间为准，预计时间仅供参考")


class TestParse(unittest.TestCase):
    def test_parse_happy(self):
        row = cb.parse_detail(HEADER, LEFT)
        self.assertIsNotNone(row)
        self.assertEqual(row["fno"], "HO1254")
        self.assertEqual(row["airline"], "吉祥航空")
        self.assertEqual(row["dep"], "21:25")
        self.assertEqual(row["arr"], "23:40")
        self.assertEqual(row["from"], "北京大兴")
        self.assertEqual(row["to"], "上海浦东")
        self.assertEqual(row["dep_terminal"], "T2")
        self.assertEqual(row["arr_terminal"], "")
        self.assertEqual(row["src"], "ctrip-detail")

    def test_parse_empty(self):
        self.assertIsNone(cb.parse_detail("", ""))
        self.assertIsNone(cb.parse_detail("吉祥航空 | 航班计划",
                                          "北京 | 上海 | 21:25"))

    def test_parse_ckpt(self):
        row = cb.parse_detail(
            "四川航空 3U8971 | 航班计划",
            "重庆江北 | T3 | 上海浦东 | T2 | 07:15 | 09:40")
        self.assertEqual(row["fno"], "3U8971")
        self.assertEqual(row["from"], "重庆江北")
        self.assertEqual(row["to"], "上海浦东")
        self.assertEqual(row["dep"], "07:15")
        self.assertEqual(row["arr"], "09:40")
        self.assertEqual(row["dep_terminal"], "T3")
        self.assertEqual(row["arr_terminal"], "T2")

    def test_parse_dual_terminal(self):
        row = cb.parse_detail(
            "海南航空 HU7605 | 航班计划",
            "北京首都 | T2 | 上海浦东 | T2 | 15:35 | 17:45")
        self.assertEqual(row["from"], "北京首都")
        self.assertEqual(row["to"], "上海浦东")
        self.assertEqual(row["dep_terminal"], "T2")
        self.assertEqual(row["arr_terminal"], "T2")
        self.assertEqual(row["dep"], "15:35")
        self.assertEqual(row["arr"], "17:45")


ROUTE = {"from_city": "北京", "to_city": "上海",
         "obs": [{"fno": "ho1254", "date": "2026-10-25"},
                 {"fno": "MU5137", "date": "2026-10-20"},
                 {"fno": "HO1254", "date": "2026-10-18"},
                 {"fno": "OLD1", "date": "2026-01-01"},
                 {"fno": "HO9999", "date": "2026-10-25",
                  "dep": "08:00"}]}


class TestTargets(unittest.TestCase):
    def test_earliest_first_and_filters(self):
        ts = cb.targets({"routes": {"r1": ROUTE}}, max_fnos=4,
                        today=_dt.date(2026, 9, 17))
        self.assertEqual(ts[0], {"fno": "HO1254",
                                 "date": "2026-10-18"})
        self.assertEqual([t["fno"] for t in ts], ["HO1254", "MU5137"])

    def test_past_and_timed_rows_skipped(self):
        h = {"routes": {"r": {"from_city": "北京",
                              "to_city": "上海",
                              "obs": [{"fno": "XX111",
                                       "date": "2026-01-01"},
                                      {"fno": "XX222",
                                       "date": "2026-10-25",
                                       "arr": "23:00"}]}}}
        self.assertEqual(cb.targets(h, today=_dt.date(2026, 9, 17)),
                         [])

    def test_cross_route_earliest_merge(self):
        h = {"routes": {"a": {"from_city": "北京", "to_city": "上海",
                             "obs": [{"fno": "CA1888",
                                      "date": "2026-10-22"}]},
                        "b": {"from_city": "杭州", "to_city": "广州",
                              "obs": [{"fno": "CA1888",
                                       "date": "2026-10-19"}]}}}
        ts = cb.targets(h, today=_dt.date(2026, 9, 17))
        self.assertEqual(ts, [{"fno": "CA1888",
                               "date": "2026-10-19"}])


DOW = str(_dt.date(2026, 10, 25).weekday())


class TestMerge(unittest.TestCase):
    def test_new_dow_deposit(self):
        db = {"fmt": 2, "updated": 0, "flights": {}}
        self.assertTrue(cb._merge_row(
            db, cb.parse_detail(HEADER, LEFT), "2026-10-25"))
        ent = db["flights"]["HO1254"]["dows"][DOW]
        self.assertEqual(ent["dep"], "21:25")
        self.assertEqual(ent["src"], "ctrip-detail")

    def test_airport_board_authoritative(self):
        db = {"fmt": 2, "updated": 0,
              "flights": {"HO1254": {"dows": {DOW: {
                  "dep": "22:00", "arr": "00:20",
                  "from": "北京大兴", "to": "上海浦东",
                  "airline": "吉祥航空",
                  "src": "airport-board"}}}}}
        row = cb.parse_detail(HEADER, LEFT)
        self.assertFalse(cb._merge_row(db, row, "2026-10-25"))
        self.assertEqual(db["flights"]["HO1254"]["dows"][DOW]["dep"],
                         "22:00")

    def test_same_tier_refresh(self):
        db = {"fmt": 2, "updated": 0,
              "flights": {"HO1254": {"dows": {DOW: {
                  "dep": "22:10", "arr": "00:30",
                  "from": "北京大兴", "to": "上海浦东",
                  "airline": "吉祥航空",
                  "src": "ctrip-detail"}}}}}
        row = cb.parse_detail(HEADER, LEFT)
        self.assertTrue(cb._merge_row(db, row, "2026-10-25"))
        self.assertEqual(db["flights"]["HO1254"]["dows"][DOW]["dep"],
                         "21:25")


class TestApplyExact(unittest.TestCase):
    def _fresh(self):
        import copy
        return copy.deepcopy({"routes": {"r1": ROUTE}})

    def test_write_once(self):
        h = self._fresh()
        row = cb.parse_detail(HEADER, LEFT)
        self.assertEqual(cb._apply_exact(h, row, "2026-10-25"), 1)
        o = h["routes"]["r1"]["obs"][0]
        self.assertEqual(o["dep"], "21:25")
        self.assertEqual(o["arr"], "23:40")
        self.assertEqual(o["tsrc"], "ctrip-detail")
        self.assertEqual(cb._apply_exact(h, row, "2026-10-25"), 0)

    def test_city_contract(self):
        h = {"routes": {"rq": {"from_city": "重庆",
                               "to_city": "上海",
                               "obs": [{"fno": "HO1254",
                                        "date": "2026-10-25"}]}}}
        row = cb.parse_detail(HEADER, LEFT)
        self.assertEqual(cb._apply_exact(h, row, "2026-10-25"), 0)


class TestCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.today = _dt.date.today().isoformat()
        self._orig = cb.cb_launch
        self.addCleanup(setattr, cb, "cb_launch", self._orig)

    def test_failure_burns_ledger_no_neg(self):
        calls = []

        def boom(nc, dd, fno, date_iso):
            calls.append(1)
            raise RuntimeError("stub offline")

        cb.cb_launch = boom
        before = cb._log_count(self.tmp, self.today)
        with self.assertRaises(RuntimeError):
            cb.fetch_flight({}, self.tmp, "CZ8879", "2026-10-16")
        self.assertEqual(cb._log_count(self.tmp, self.today),
                         before + 1)
        self.assertFalse(cb.neg_hit(self.tmp, "CZ8879",
                                    "2026-10-16"))

    def test_cache_hit_and_neg(self):
        p = cb._cache_path(self.tmp, "CZ8879", "2026-10-16")
        _atomic_write(p, {"ts": time.time(),
                          "row": {"fno": "CZ8879", "dep": "12:00",
                                  "arr": "14:10"},
                          "neg": False})
        row, how = cb.fetch_flight({}, self.tmp, "CZ8879",
                                   "2026-10-16")
        self.assertEqual(how, "cache")
        self.assertEqual(row["dep"], "12:00")
        p2 = cb._cache_path(self.tmp, "XX1234", "2026-10-16")
        _atomic_write(p2, {"ts": time.time(), "row": None,
                           "neg": True})
        row2, how2 = cb.fetch_flight({}, self.tmp, "XX1234",
                                     "2026-10-16")
        self.assertEqual(how2, "neg-cache")
        self.assertIsNone(row2)


class TestLedger(unittest.TestCase):
    def test_bump_and_count(self):
        tmp = tempfile.mkdtemp()
        today = _dt.date.today().isoformat()
        for _ in range(3):
            cb._bump_log(tmp, today)
        self.assertEqual(cb._log_count(tmp, today), 3)


if __name__ == "__main__":
    unittest.main()
