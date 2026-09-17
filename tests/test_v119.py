# -*- coding: utf-8 -*-
"""v1.19: spend the Shanghai-board budget on bookable rows.

Live checks showed CZ3440/CZ3480 are not on the Shanghai board (two
directions x two offsets, all empty) while the budget still pays 4
queries per day for them; and PEK->SHA shows 2/8 because CZ8803's
October dows live in cache-hit territory while CZ8879 (12:00 dep)
burned first. This round: negative cache, earliest-date priority,
force bypass for the ops tool, and a +1d marker for cross-midnight
arrivals so 22:25-22:10 reads as overnight, not negative."""
import datetime as dt
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.sh_board import dow_targets, sh_fill


class _Resp:
    def __init__(self):
        pass

    def raise_for_status(self):
        return None

    def json(self):
        return {"success": True, "data": {"flightList": "[]"}}


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append((data, headers))
        return _Resp()


def _hist(*dates):
    return {"routes": {"r1": {
        "from_city": "北京", "to_city": "上海", "obs": [
            {"date": d, "fno": "CZ8803"} for d in dates]}}}


class TestEarliestFirst(unittest.TestCase):
    def test_soonest_departure_burns_first(self):
        # 2026-10-28 Wed, 2026-10-19 Mon; window covers Monday
        hist = _hist("2026-10-28",  # Wednesday, CZ8803 covers it
                     "2026-10-19")  # Monday, no dow entry -> prio
        out = dow_targets(hist, {"flights": {}}, window_dows={"0", "1"})
        # both dates share the fno; the MISSING Monday (dow 0) must
        # lead the needed set because 10-19 departs before 10-28
        self.assertEqual(out, [{"fno": "CZ8803", "direction": 2,
                                "dows": ["0", "2"]}])


class TestForceBypass(unittest.TestCase):
    def test_sh_fill_forwards_force_to_fetch(self):
        tmp = os.path.join(os.environ.get("TEMP", "."), "sh119")
        shutil.rmtree(tmp, ignore_errors=True)  # no cross-run state
        os.makedirs(tmp, exist_ok=True)
        sess = FakeSession()
        # dynamic dates: today/tomorrow always sit in the queryable
        # window regardless of which weekday the suite runs on
        today = dt.date.today()
        sh_fill(sess, {"sh_pace": 0}, tmp,
                _hist(today.isoformat(), (today + dt.timedelta(days=1)).isoformat()),
                force=True)
        self.assertEqual(len(sess.calls), 2)  # off0 + off1, no cache


class TestCrossDay(unittest.TestCase):
    def test_timetable_rows_carry_cross_day(self):
        from core.cabin_monitor import history_timetable
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-10-19", "fno": "CZ8803", "price": 900.0,
                 "dep": "22:25", "arr": "22:10",
                 "cross_day": True}]}}}
        g = history_timetable(hist)[0]
        self.assertTrue(g["rows"][0]["cross_day"])
        self.assertEqual(g["timed"], 1)

    def test_rows_without_flag_stay_clean(self):
        from core.cabin_monitor import history_timetable
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-10-19", "fno": "HO1254", "price": 800.0,
                 "dep": "21:25", "arr": "23:35"}]}}}
        g = history_timetable(hist)[0]
        self.assertFalse(g["rows"][0]["cross_day"])


class TestWiring(unittest.TestCase):
    def test_frontend_marker_and_tool_force_wired(self):
        with open("webui/static/app.js", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("cabin-tt-cross", js)
        self.assertIn("跨零点到达", js)
        with open("webui/static/style.css", encoding="utf-8") as f:
            self.assertIn("em.cabin-tt-cross", f.read())
        with open("tools/sh_cabin_fill.py", encoding="utf-8") as f:
            tool = f.read()
        self.assertIn("--force", tool)
        self.assertIn("force=args.force", tool)


if __name__ == "__main__":
    unittest.main(verbosity=2)
