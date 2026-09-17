# -*- coding: utf-8 -*-
"""v1.20: cap is absolute; empty-board answers stop costing slots.

v1.19's live run exposed a privilege escalation: force=True skipped
the daily 24-query cap along with the row cache, burning the ledger
to 32/24. And flights the board does not know (CZ3440/CZ3480 class)
kept re-occupying plan slots every day. This round: force only
refreshes rows under the cap; success-empty answers land a 24h
negative cache that returns neg-cache for free and vacates its plan
slot so real flights get the budget."""
import datetime as dt
import json
import os
import shutil
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.sh_board import fetch_flight, neg_hit, sh_fill


class _Resp:
    def raise_for_status(self):
        return None

    def __init__(self, rows):
        self._rows = rows

    def json(self):
        return {"success": True,
                "data": {"flightList": json.dumps(self._rows)}}


class FakeSession:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else []
        self.calls = 0

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls += 1
        return _Resp(self.rows)


def _tmp(name):
    p = os.path.join(os.environ.get("TEMP", "."), name)
    shutil.rmtree(p, ignore_errors=True)  # fresh per run
    os.makedirs(p, exist_ok=True)
    return p


def _hist(*dates):
    return {"routes": {"r1": {
        "from_city": "北京", "to_city": "上海", "obs": [
            {"date": d, "fno": "CZ8803"} for d in dates]}}}


class TestCapAbsolute(unittest.TestCase):
    def test_force_cannot_bypass_daily_cap(self):
        tmp = _tmp("sh120_cap")
        # fill the ledger to the cap
        from core.sh_board import SH_LOG_NAME, SH_LOG_KIND
        with open(os.path.join(tmp, SH_LOG_NAME), "w",
                  encoding="utf-8") as f:
            json.dump({SH_LOG_KIND: {
                dt.date.today().isoformat(): 24}}, f)
        rows, how = fetch_flight(FakeSession(), {}, "CZ8803", 2, 0,
                                 tmp, force=True)
        self.assertEqual(how, "capped")
        self.assertEqual(rows, [])

    def test_force_refreshes_rows_when_under_cap(self):
        tmp = _tmp("sh120_force")
        s = FakeSession(rows=[{
            "主航班号": "HO1254",
            "计划出发时间": "2026-09-17 21:25:00",
            "计划到达时间": "2026-09-17 23:35:00",
            "出发地": "北京 大兴", "目的地": "上海 虹桥"}])
        rows, how = fetch_flight(s, {}, "HO1254", 2, 0, tmp, force=True)
        self.assertEqual((how, len(rows)), ("net", 1))
        # second force call still hits the network (row cache skipped)
        rows2, how2 = fetch_flight(s, {}, "HO1254", 2, 0, tmp, force=True)
        self.assertEqual(how2, "net")
        self.assertEqual(s.calls, 2)


class TestNegCache(unittest.TestCase):
    def test_empty_answer_is_neg_cached_and_free(self):
        tmp = _tmp("sh120_neg")
        s = FakeSession(rows=[])
        rows, how = fetch_flight(s, {}, "CZ3440", 2, 0, tmp)
        self.assertEqual((how, rows), ("net", []))
        self.assertEqual(s.calls, 1)
        self.assertTrue(neg_hit(tmp, "CZ3440", 2, 0))
        # within TTL: zero network, zero budget
        rows2, how2 = fetch_flight(s, {}, "CZ3440", 2, 0, tmp)
        self.assertEqual(how2, "neg-cache")
        self.assertEqual(s.calls, 1)

    def test_neg_cache_expires_after_24h(self):
        tmp = _tmp("sh120_negexp")
        path = os.path.join(
            tmp, "board_sh_CZ3440_2_0.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time() - 25 * 3600,
                       "rows": [], "neg": True}, f)
        self.assertFalse(neg_hit(tmp, "CZ3440", 2, 0))

    def test_nonempty_rows_never_neg(self):
        tmp = _tmp("sh120_nonneg")
        s = FakeSession(rows=[{
            "主航班号": "HO1254",
            "计划出发时间": "2026-09-17 21:25:00",
            "计划到达时间": "2026-09-17 23:35:00"}])
        fetch_flight(s, {}, "HO1254", 2, 0, tmp)
        self.assertFalse(neg_hit(tmp, "HO1254", 2, 0))

    def test_neg_vacates_plan_slot(self):
        tmp = _tmp("sh120_slot")
        for off in (0, 1):
            with open(os.path.join(
                    tmp, "board_sh_CZ3440_2_%d.json" % off), "w",
                    encoding="utf-8") as f:
                json.dump({"ts": time.time(), "rows": [],
                           "neg": True}, f)
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-10-19", "fno": "CZ3440"},
                {"date": "2026-10-20", "fno": "HO1254"}]}}}
        # 10-19 Monday, 10-20 Tuesday; window covers both
        from core.sh_board import dow_targets
        plan_sources = dow_targets(hist, {"flights": {}}, max_fnos=4,
                                   window_dows={"0", "1"})
        # emulate sh_fill's slot filter inline (its loop is inside
        # sh_fill; here we assert the predicate the filter uses)
        kept = [t for t in plan_sources
                if not all(neg_hit(tmp, t["fno"], t["direction"], o)
                           for o in (0, 1))]
        self.assertEqual([t["fno"] for t in kept], ["HO1254"])


class TestWiring(unittest.TestCase):
    def test_sh_fill_counts_neg_and_skips_slots(self):
        tmp = _tmp("sh120_fill")
        for off in (0, 1):
            with open(os.path.join(
                    tmp, "board_sh_CZ3440_2_%d.json" % off), "w",
                    encoding="utf-8") as f:
                json.dump({"ts": time.time(), "rows": [],
                           "neg": True}, f)
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-10-19", "fno": "CZ3440"}]}}}
        s = FakeSession()
        stats = sh_fill(s, {"sh_pace": 0}, tmp, hist)
        self.assertEqual(stats.get("neg", 0) + 0, 0)  # no plan slot
        self.assertEqual(s.calls, 0)  # zero network for neg fno

    def test_frontend_renders_sh_fill_stats(self):
        with open("webui/static/app.js", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("patrol.sh_fill", js)
        self.assertIn("上海板时刻", js)
        self.assertIn("负缓存", js)


if __name__ == "__main__":
    unittest.main(verbosity=2)
