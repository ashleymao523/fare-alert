# -*- coding: utf-8 -*-
"""v1.32 checks: business-cabin precision completion.

The CDP browser itself is NOT launched - _capture_target runs
against the FakeCdp answering canned miners, patrol_fill has its
capture_batch monkeypatched, so the pure plumbing (precision-gap
targets, whole-list cabin mining, capture_day cabin bucket,
webui+frontend wiring) is verified without browser minutes.
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


class TestV132(unittest.TestCase):

    def setUp(self):
        import core.cdp_cabin as cc
        self.cc = cc
        self._real_time = cc.time
        cc.time = FakeTime

    def tearDown(self):
        self.cc.time = self._real_time

    def test_01_precision_gap_dates(self):
        from core.cabin_monitor import precision_gap_dates
        hist = {"routes": {"leg-A-B": {"obs": [
            {"date": "2026-10-01", "price": 900, "src": "booking",
             "dep": "08:00", "arr": "10:00"},
            {"date": "2026-10-02", "price": 950, "src": "qunar",
             "dep": "09:00", "arr": "11:00"},
            {"date": "2026-10-03", "price": 910, "src": "qunar"},
            {"date": "2026-10-03", "price": 1200, "src": "booking"},
        ]}}}
        gaps = precision_gap_dates(hist, "leg-A-B",
                                   "2026-09-28", "2026-10-06")
        # 10-01 is estimate-only -> gap; 10-02 precise; 10-03 has a
        # precise row; unobserved dates are NOT gaps
        self.assertEqual(gaps, ["2026-10-01"])
        self.assertEqual(
            precision_gap_dates(hist, "leg-missing",
                                "2026-10-01", "2026-10-06"), [])
        self.assertEqual(
            precision_gap_dates({}, "leg-A-B", "bad", "2026-10-01"), [])

    def test_02_business_whole_list_mining(self):
        from core.cdp_cabin import _capture_target
        cdp = FakeCdp(list_rows=[
            {"p": 1290, "no": "MU5138", "dep": "07:00", "arr": "09:10"},
            {"p": 1075, "no": "MU5231", "dep": "12:40", "arr": "15:05"},
            {"p": 1180, "no": "HU7421", "dep": "16:55", "arr": "19:40"},
        ])
        sink = []
        with tempfile.TemporaryDirectory() as td:
            n = _capture_target(cdp, "北京", "上海", "2026-10-11",
                                "business", td, rows_sink=sink)
            # bucket keys by date: the lowest offer wins the slot
            self.assertEqual(n, 1)
            cache = json.load(open(os.path.join(
                td, "point_fill_cache.json"), encoding="utf-8"))
        ent = cache["cdp-cabin-北京-上海"]["2026-10-11"]
        # v1.27 key + cabin tag; the LOWEST of the visible offers
        self.assertEqual(ent["cabin"], "business")
        self.assertEqual(ent["flight_no"], "MU5231")
        self.assertEqual(ent["total"], 1075.0)
        # every visible business offer rode the sink
        self.assertEqual(len(sink), 3)
        nos = sorted(r["flight_no"] for r in sink)
        self.assertEqual(nos, ["HU7421", "MU5138", "MU5231"])

    def test_03_business_miner_fallback(self):
        from core.cdp_cabin import _capture_target
        cdp = FakeCdp(list_rows=[], best={
            "p": 1290, "no": "MU5138", "dep": "07:00", "arr": "09:10"})
        with tempfile.TemporaryDirectory() as td:
            n = _capture_target(cdp, "北京", "上海", "2026-10-11",
                                "business", td)
            self.assertEqual(n, 1)
            cache = json.load(open(os.path.join(
                td, "point_fill_cache.json"), encoding="utf-8"))
        ent = cache["cdp-cabin-北京-上海"]["2026-10-11"]
        self.assertEqual(ent["flight_no"], "MU5138")
        self.assertEqual(ent["cabin"], "business")

    def test_04_first_cabin_tag_preserved(self):
        from core.cdp_cabin import _capture_target
        cdp = FakeCdp(list_rows=[
            {"p": 1990, "no": "CA1501", "dep": "08:30", "arr": "10:45"}])
        with tempfile.TemporaryDirectory() as td:
            _capture_target(cdp, "北京", "上海", "2026-10-11",
                            "first", td)
            cache = json.load(open(os.path.join(
                td, "point_fill_cache.json"), encoding="utf-8"))
        ent = cache["cdp-cabin-北京-上海"]["2026-10-11"]
        self.assertEqual(ent["cabin"], "first")

    def test_05_capture_day_cabin_bucket(self):
        import core.cdp_cabin as cc
        seen = {}
        td = __import__("tempfile").mkdtemp()

        def fake_batch(net_cfg, data_dir, targets, log=None,
                       rows_sink=None, wait_s=12.0):
            seen["targets"] = targets
            if rows_sink is not None:
                rows_sink.extend([
                    {"date": targets[0]["date"], "total": 1075.0,
                     "flight_no": "MU5231", "dep_time": "12:40",
                     "arr_time": "15:05", "cabin": "business"}])
            return 1

        real = cc.capture_batch
        cc.capture_batch = fake_batch
        try:
            out = cc.capture_day({}, td, "北京", "上海",
                                 "2026-10-11", "route-x",
                                 cabin="business")
        finally:
            cc.capture_batch = real
            __import__("shutil").rmtree(td, ignore_errors=True)
        t = seen["targets"][0]
        self.assertEqual(t["cabin"], "business")
        self.assertEqual(t["cache_id"], "cdp-cabin-北京-上海")
        self.assertEqual(out["rows"][0]["flight_no"], "MU5231")
        self.assertEqual(out["stored"], 1)

    def test_06_patrol_targets_precision_gaps(self):
        """The v1.32 fix: time cells full must NOT send the patrol
        to sleep while booking-only dates remain."""
        from core.cabin_monitor import record_low
        import core.cdp_cabin as cc
        hist = {"routes": {}}
        # every obs timed (dep/arr) BUT estimate-sourced -> no time
        # gap, only precision gaps
        for d in ("2026-10-01", "2026-10-02", "2026-10-03"):
            record_low(hist, "leg-北京-杭州", "北京", "杭州",
                       "business", d, 900.0 + int(d[-2:]),
                       fno="MU5138", dep="07:00", arr="09:10",
                       source="booking")
        seen = {}

        def fake_batch(net_cfg, data_dir, targets, log=None,
                       rows_sink=None, wait_s=12.0):
            seen["targets"] = targets
            return len(targets)

        cw = {"enabled": True, "cdp_capture": True,
              "to_cities": ["杭州"], "watch_from_cities": ["北京"],
              "cdp_dates_per_round": 2, "cdp_capture_daily_cap": 24}
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "cabin_history.json"), "w",
                      encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False)
            real = cc.capture_batch
            real_load = cc._cabin_history_load if hasattr(
                cc, "_cabin_history_load") else None
            cc.capture_batch = fake_batch
            try:
                info = cc.patrol_fill(cw, [], td, throttle_hits=1)
            finally:
                cc.capture_batch = real
        self.assertNotIn("skipped", info)
        self.assertEqual(info.get("targets"), 2)
        dates = [t["date"] for t in seen["targets"]]
        self.assertEqual(dates, ["2026-10-01", "2026-10-02"])
        self.assertTrue(all(
            t["from_city"] == "北京" and t["to_city"] == "杭州"
            for t in seen["targets"]))

    def test_07_webui_wiring(self):
        src = open(os.path.join("webui.py"), encoding="utf-8").read()
        self.assertIn('cabin = str(body.get("cabin") or "")', src)
        self.assertIn('"bad cabin"', src)
        self.assertIn("cabin=cabin)", src)
        self.assertIn('"cabin": cabin', src)
        # watch legs without an economy snapshot route must pass
        self.assertIn('if not rid and not cabin', src)

    def test_08_frontend_wiring_and_tokens(self):
        js = open(os.path.join("webui", "static", "app.js"),
                  encoding="utf-8").read()
        self.assertIn("function dayCapKey(route, date, cabin)", js)
        self.assertIn("cabin: cabin", js)          # POST body
        self.assertIn('renderDayCap(capBox, route, d.date, "")', js)
        self.assertIn(
            'renderDayCap(capBiz, route, d.date, "business")', js)
        css = open(os.path.join("webui", "static", "style.css"),
                   encoding="utf-8").read()
        self.assertIn(".day-cap-wrap {", css)
        for line in css.splitlines():
            if line.strip().startswith("background:") and "#" in line \
                    and "var(" not in line:
                self.fail("raw hex in css: " + line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
