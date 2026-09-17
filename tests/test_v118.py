# -*- coding: utf-8 -*-
"""v1.18: Shanghai official board -> exact business-cabin times.

The user flagged missing times on Shanghai legs (the HGH board
cannot see them, and Booking refills were grounded by 429). The
metro's own zero-key Avinex board answers per-date plan times for
today/tomorrow plus dow deposits for the borrow ladder."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.sh_board import (
    apply_exact_times, dow_targets, exact_targets, fetch_flight,
    merge_sh_rows, sh_fill, _city, _hm, _normalize,
)


def _row(date, dep, arr, fno="HO1254", src="北京", dst="上海"):
    return {"date": date, "fno": fno, "dep": dep, "arr": arr,
            "from": src, "to": dst, "airline": "吉祥",
            "terminal": "T2", "src": "shanghai-board"}


class TestParse(unittest.TestCase):
    def test_city_takes_metro_prefix(self):
        self.assertEqual(_city("北京 大兴"), "北京")
        self.assertEqual(_city("上海 浦东"), "上海")
        self.assertEqual(_city(""), "")
        self.assertEqual(_city(["x"]), "")

    def test_hm_slices_plan_time(self):
        self.assertEqual(_hm("2026-09-16 21:25:00"), "21:25")
        self.assertEqual(_hm(""), "")
        self.assertEqual(_hm(None), "")

    def test_normalize_maps_official_fields(self):
        r = _normalize({
            "主航班号": " ho 1254 ",
            "计划出发时间": "2026-09-16 21:25:00",
            "计划到达时间": "2026-09-16 23:35:00",
            "出发地": "北京 大兴", "目的地": "上海 浦东",
            "航空公司": "吉祥", "候机楼": "T2"})
        self.assertEqual(r["fno"], "HO1254")
        self.assertEqual(r["dep"], "21:25")
        self.assertEqual(r["arr"], "23:35")
        self.assertEqual(r["from"], "北京")
        self.assertEqual(r["to"], "上海")
        self.assertIsNone(_normalize({"主航班号": ""}))


class TestExactTargets(unittest.TestCase):
    def test_window_direction_and_filters(self):
        hist = {"routes": {
            "rSH": {"from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-09-16", "fno": "HO1254"},
                {"date": "2026-09-18", "fno": "HO1258"},
                {"date": "2026-09-19", "fno": "HO1260"},
                {"date": "2026-09-16", "fno": "HO1252",
                 "dep": "09:00", "arr": "11:30"}]},
            "rHGH": {"from_city": "北京", "to_city": "杭州", "obs": [
                {"date": "2026-09-16", "fno": "CA1709"}]},
            "rOut": {"from_city": "上海", "to_city": "北京", "obs": [
                {"date": "2026-09-17", "fno": "HO1253"}]},
        }}
        got = exact_targets(hist, today=dt.date(2026, 9, 16))
        keys = [(t["route_id"], t["fno"], t["direction"]) for t in got]
        self.assertIn(("rSH", "HO1254", 2), keys)
        self.assertIn(("rSH", "HO1258", 2), keys)  # horizon edge
        self.assertIn(("rOut", "HO1253", 1), keys)  # departs SH
        self.assertNotIn(("rSH", "HO1260", 2), keys)  # out of window
        self.assertNotIn(("rSH", "HO1252", 2), keys)  # already timed
        self.assertNotIn(("rHGH", "CA1709", 2), keys)  # non-SH leg


class TestApplyExactTimes(unittest.TestCase):
    def test_fill_marks_tsrc(self):
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-09-16", "fno": "HO1254"}]}}}
        n = apply_exact_times(hist, [_row("2026-09-16", "21:25", "23:35")])
        self.assertEqual(n, 1)
        o = hist["routes"]["r1"]["obs"][0]
        self.assertEqual((o["dep"], o["arr"]), ("21:25", "23:35"))
        self.assertEqual(o["tsrc"], "shanghai-board")

    def test_city_contract_blocks_wrong_route(self):
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "杭州", "obs": [
                {"date": "2026-09-16", "fno": "HO1254"}]}}}
        self.assertEqual(apply_exact_times(
            hist, [_row("2026-09-16", "21:25", "23:35")]), 0)

    def test_never_overwrites_existing_times(self):
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-09-16", "fno": "HO1254",
                 "dep": "20:00", "arr": "22:30"}]}}}
        self.assertEqual(apply_exact_times(
            hist, [_row("2026-09-16", "21:25", "23:35")]), 0)
        self.assertEqual(hist["routes"]["r1"]["obs"][0]["dep"], "20:00")


class TestMergeShRows(unittest.TestCase):
    def test_deposits_own_dow(self):
        db = {"flights": {}}
        self.assertTrue(merge_sh_rows(
            db, [_row("2026-09-16", "21:25", "23:35")]))
        ent = db["flights"]["HO1254"]["dows"]["2"]  # a Wednesday
        self.assertEqual((ent["dep"], ent["src"]),
                         ("21:25", "shanghai-board"))

    def test_airport_board_stays_authoritative(self):
        db = {"flights": {"HO1254": {"dows": {"2": {
            "dep": "21:30", "arr": "23:40", "from": "", "to": "",
            "src": "airport-board"}}}}}
        self.assertTrue(merge_sh_rows(
            db, [_row("2026-09-16", "21:25", "23:35")]))
        ent = db["flights"]["HO1254"]["dows"]["2"]
        self.assertEqual((ent["dep"], ent["arr"]), ("21:30", "23:40"))
        self.assertEqual((ent["from"], ent["to"]), ("北京", "上海"))

    def test_same_tier_newest_wins_and_noop_is_quiet(self):
        db = {"flights": {"HO1254": {"dows": {"2": {
            "dep": "21:30", "arr": "23:40", "from": "北京",
            "to": "上海", "src": "amadeus-sched"}}}}}
        self.assertTrue(merge_sh_rows(
            db, [_row("2026-09-16", "21:25", "23:35")]))
        self.assertEqual(db["flights"]["HO1254"]["dows"]["2"]["dep"],
                         "21:25")
        self.assertFalse(merge_sh_rows(
            db, [_row("2026-09-16", "21:25", "23:35")]))


class TestDowTargets(unittest.TestCase):
    HIST = {"routes": {"r1": {
        "from_city": "北京", "to_city": "上海", "obs": [
            {"date": "2026-09-16", "fno": "HO1254"}]}}}

    # 2026-09-16 is a Tuesday; v1.21 window is explicit in tests
    WINDOW = {"2", "3"}  # Tuesday + Wednesday

    def test_missing_dow_queries_then_self_extinguishes(self):
        self.assertEqual(
            dow_targets(self.HIST, {"flights": {}},
                        window_dows=self.WINDOW),
            [{"fno": "HO1254", "direction": 2, "dows": ["2"]}])
        db = {"flights": {"HO1254": {"dows": {
            "2": {"dep": "21:25", "arr": "23:35"}}}}}
        self.assertEqual(
            dow_targets(self.HIST, db, window_dows=self.WINDOW), [])

    def test_max_fnos_bounds_the_run(self):
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": "2026-09-16", "fno": "HO1254"},
                {"date": "2026-09-16", "fno": "HO1258"},
                {"date": "2026-09-16", "fno": "HO1260"}]}}}
        self.assertEqual(len(dow_targets(hist, {"flights": {}},
                                         max_fnos=2,
                                         window_dows=self.WINDOW)), 2)


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


class FakeSession:
    def __init__(self, rows):
        # the real endpoint nests a JSON string inside the payload
        self.payload = {"success": True, "data": {
            "flightList": json.dumps(rows, ensure_ascii=False)}}
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(url)
        return _Resp(self.payload)


class TestFetchFlight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.today = dt.date.today().isoformat()
        raw = {"主航班号": "HO1254",
               "计划出发时间": self.today + " 21:25:00",
               "计划到达时间": self.today + " 23:35:00",
               "出发地": "北京 大兴", "目的地": "上海 浦东",
               "航空公司": "吉祥", "候机楼": "T2"}
        self.sess = FakeSession([raw])

    def test_net_then_cache(self):
        rows, how = fetch_flight(self.sess, {}, "HO1254", 2, 0, self.tmp)
        self.assertEqual((how, len(rows)), ("net", 1))
        rows, how = fetch_flight(self.sess, {}, "HO1254", 2, 0, self.tmp)
        self.assertEqual((how, len(rows)), ("cache", 1))
        self.assertEqual(len(self.sess.calls), 1)

    def test_daily_cap_is_a_noop_not_an_error(self):
        with open(os.path.join(self.tmp, "board_fetch_log.json"),
                  "w", encoding="utf-8") as f:
            json.dump({"sh_board": {self.today: 24}}, f)
        rows, how = fetch_flight(self.sess, {}, "HO1254", 2, 0, self.tmp)
        self.assertEqual((how, rows), ("capped", []))
        self.assertEqual(self.sess.calls, [])


class TestShFillDriver(unittest.TestCase):
    def test_exact_fill_and_dow_deposit(self):
        tmp = tempfile.mkdtemp()
        today = dt.date.today().isoformat()
        hist = {"routes": {"r1": {
            "from_city": "北京", "to_city": "上海", "obs": [
                {"date": today, "fno": "HO1254", "cabin": "business",
                 "price": 1277.0}]}}}
        raw = {"主航班号": "HO1254",
               "计划出发时间": today + " 21:25:00",
               "计划到达时间": today + " 23:35:00",
               "出发地": "北京 大兴", "目的地": "上海 浦东"}
        stats = sh_fill(FakeSession([raw]), {"sh_pace": 0}, tmp, hist)
        self.assertEqual(stats["exact"], 1)
        o = hist["routes"]["r1"]["obs"][0]
        self.assertEqual((o["dep"], o["arr"], o["tsrc"]),
                         ("21:25", "23:35", "shanghai-board"))
        with open(os.path.join(tmp, "flight_sched_db.json"),
                  encoding="utf-8") as f:
            db = json.load(f)
        dow = str(dt.date.today().weekday())
        self.assertEqual(
            db["flights"]["HO1254"]["dows"][dow]["dep"], "21:25")


class TestWiring(unittest.TestCase):
    def test_backend_frontend_and_ops_tool_wired(self):
        with open("main.py", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("from core.sh_board import sh_fill", src)
        self.assertIn('info["sh_fill"] = sh_fill(', src)
        with open("webui.py", encoding="utf-8") as f:
            self.assertIn('"sh_fill": pstate.get("sh_fill")',
                          f.read())
        with open("webui/static/app.js", encoding="utf-8") as f:
            self.assertIn("shanghai-board", f.read())
        with open("webui/static/style.css", encoding="utf-8") as f:
            self.assertIn("cabin-tt-sh", f.read())
        self.assertTrue(os.path.exists("tools/sh_cabin_fill.py"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
