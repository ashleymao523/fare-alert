# -*- coding: utf-8 -*-
"""v1.31 checks: economy day capture (whole-list mining + 24h timeline).

The CDP browser itself is NOT launched here - _capture_target is
exercised against a FakeCdp answering canned miners, so the pure
plumbing (tap plan, list mining, put_rows bucket, rows_sink,
capture_day sort/passthrough, webui+frontend wiring) is verified
without browser minutes.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


class FakeTime(object):
    _t = 1000.0

    @classmethod
    def time(cls):
        return cls._t

    @staticmethod
    def sleep(_s):
        return None


class FakeCdp(object):
    """Answers the exact JS constants _capture_target evaluates."""

    def __init__(self, list_rows=None, best=None, url="ok"):
        self.list_rows = list_rows or []
        self.best = best
        self.url = url
        self.navs = []

    def nav(self, u):
        self.navs.append(u)

    def ev(self, js):
        if js == "location.href":
            return self.url
        if "return rows.slice(0,12)" in js:
            return self.list_rows
        if "return best" in js:
            return self.best
        return "tapped"


class TestV131(unittest.TestCase):

    def setUp(self):
        import core.cdp_cabin as cc
        self.cc = cc
        self._real_time = cc.time
        cc.time = FakeTime

    def tearDown(self):
        self.cc.time = self._real_time

    def test_01_tap_plan(self):
        from core.cdp_cabin import _tap_plan
        self.assertEqual(len(_tap_plan("business")), 4)
        self.assertEqual(len(_tap_plan("first")), 4)
        self.assertEqual(_tap_plan(""), [])
        self.assertEqual(_tap_plan("economy"), [])
        self.assertEqual(_tap_plan(None), [])

    def test_02_list_miner_contract(self):
        from core.cdp_cabin import LIST_MINER_JS
        self.assertIn("cardOf", LIST_MINER_JS)
        self.assertIn("rows.slice(0,12)", LIST_MINER_JS)
        self.assertIn("a.p-b.p", LIST_MINER_JS)  # sorted by price

    def test_03_economy_capture_stores_lowest_per_date(self):
        from core.cdp_cabin import _capture_target
        cdp = FakeCdp(list_rows=[
            {"p": 1290, "no": "MU5138", "dep": "07:00", "arr": "09:10"},
            {"p": 980, "no": "KN5955", "dep": "16:30", "arr": "18:40"},
        ])
        sink = []
        with tempfile.TemporaryDirectory() as td:
            n = _capture_target(
                cdp, "杭州", "重庆", "2026-10-10", "", td,
                rows_sink=sink, cache_id="杭州-重庆")
            self.assertEqual(n, 1)
            cache = json.load(open(os.path.join(
                td, "point_fill_cache.json"), encoding="utf-8"))
            ent = cache["杭州-重庆"]["2026-10-10"]
            self.assertEqual(ent["flight_no"], "KN5955")  # lowest wins
            self.assertEqual(ent["dep_time"], "16:30")
            self.assertEqual(ent["cabin"], "")  # economy row
        # the WHOLE list rode the sink for the timeline
        self.assertEqual(len(sink), 2)
        nos = [r["flight_no"] for r in sink]
        # order-free: the virtual-scroll merge sorts by price
        self.assertCountEqual(nos, ["MU5138", "KN5955"])
        self.assertEqual(sink[0]["flight_no"], "KN5955")
        self.assertEqual(sink[0]["total"], 980)

    def test_04_business_path_unchanged(self):
        from core.cdp_cabin import _capture_target
        cdp = FakeCdp(best={"p": 1290, "no": "MU5138",
                            "dep": "07:00", "arr": "09:10"})
        with tempfile.TemporaryDirectory() as td:
            n = _capture_target(cdp, "北京", "上海", "2026-10-11",
                                "business", td)
            self.assertEqual(n, 1)
            cache = json.load(open(os.path.join(
                td, "point_fill_cache.json"), encoding="utf-8"))
        # default bucket keeps the v1.27 key, cabin tag preserved
        ent = cache["cdp-cabin-北京-上海"]["2026-10-11"]
        self.assertEqual(ent["cabin"], "business")
        self.assertEqual(ent["flight_no"], "MU5138")

    def test_05_capture_day_sorts_by_dep_and_queues(self):
        import core.cdp_cabin as cc
        import core.point_fill as pf
        rows = [{"date": "2026-10-10", "total": 1290.0,
                 "flight_no": "MU5138", "dep_time": "07:00",
                 "arr_time": "09:10", "cabin": "",
                 "from_city": "杭州", "to_city": "重庆"},
                {"date": "2026-10-10", "total": 980.0,
                 "flight_no": "KN5955", "dep_time": "16:30",
                 "arr_time": "18:40", "cabin": "",
                 "from_city": "杭州", "to_city": "重庆"}]
        seen = {}

        def fake_batch(net_cfg, data_dir, targets, log=None,
                       wait_s=12.0, home_s=4.0, rows_sink=None):
            seen["targets"] = targets
            if rows_sink is not None:
                rows_sink.extend(rows)
            return 1

        queued = {}

        def fake_queue(data_dir, rs):
            queued["n"] = len(rs)
            return len(rs)

        real_batch, real_q = cc.capture_batch, pf.queue_sched_deposit
        cc.capture_batch, pf.queue_sched_deposit = fake_batch, fake_queue
        try:
            with tempfile.TemporaryDirectory() as td:
                out = cc.capture_day({}, td, "杭州", "重庆",
                                     "2026-10-10", "杭州-重庆",
                                     tax=120.0)
        finally:
            cc.capture_batch, pf.queue_sched_deposit = real_batch, real_q
        t = seen["targets"][0]
        self.assertEqual(t["cabin"], "")          # economy board
        self.assertEqual(t["cache_id"], "杭州-重庆")  # route bucket
        self.assertEqual(t["tax"], 120.0)         # bare-price semantics
        self.assertEqual(out["stored"], 1)
        self.assertEqual(queued["n"], 2)
        # timeline order: dep_time ascending, cheapest flag upstream
        self.assertEqual([r["flight_no"] for r in out["rows"]],
                         ["MU5138", "KN5955"])

    def test_06_webui_wiring(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        w = open(os.path.join(base, "webui.py"), encoding="utf-8").read()
        self.assertIn("/api/tasks/cdp-day/run", w)
        self.assertIn("capture_day(", w)
        self.assertIn("tax=tax_amount(", w)      # bare semantics
        self.assertIn("cdp_cabin_ledger.json", w)  # shared budget
        self.assertIn("patch_snapshot_deals", w)   # immediate calendar

    def test_07_frontend_wiring(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        js = open(os.path.join(base, "webui", "static", "app.js"),
                  encoding="utf-8").read()
        css = open(os.path.join(base, "webui", "static", "style.css"),
                   encoding="utf-8").read()
        self.assertIn("cdp-day/run", js)
        self.assertIn("dayTimePos", js)
        self.assertIn("day-tl24", js)          # 24h timeline strip
        self.assertIn("renderDayCap", js)
        self.assertIn("day-cap-row", js)
        self.assertIn(".day-tl24-dot", css)
        self.assertIn(".day-cap-row.min", css)
        # tokens only - no raw hex in the new block
        block = css.split(".day-cap {", 1)[1].split(".cabin-leg-meta", 1)[0]
        import re
        self.assertFalse(re.search(r"#[0-9a-fA-F]{3,8}\b", block))


if __name__ == "__main__":
    unittest.main(verbosity=2)
