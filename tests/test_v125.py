# -*- coding: utf-8 -*-
"""v1.25 acceptance: per-leg business-cabin thresholds.

route_thresholds["出发>目的"] overrides the global threshold_total;
keys accept Chinese or IATA spellings (normalized via core.intl);
evaluate_alert judges each leg by its own line; webui /api/cabin
stamps the effective threshold on timetable+board rows; config
validation cleans junk entries; cache-bust v=33 and CODE_VERSION
stay in lock-step.
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import evaluate_alert, leg_threshold, load_config
import webui


def _cw():
    return {
        "enabled": True,
        "threshold_total": 1000.0,
        "route_thresholds": {"北京>上海": 1300.0},
    }


def _hist():
    return {"routes": {
        "patrol-北京-上海": {
            "from_city": "北京", "to_city": "上海",
            "obs": [{"date": "2026-10-01", "cabin": "business",
                     "price": 1277.2, "fno": "HO1254"}]},
        "patrol-重庆-上海": {
            "from_city": "重庆", "to_city": "上海",
            "obs": [{"date": "2026-10-02", "cabin": "business",
                     "price": 1467.6, "fno": "MU5421"}]},
    }}


class TestV125(unittest.TestCase):
    def test_01_leg_threshold_exact_and_iata(self):
        cw = _cw()
        self.assertEqual(leg_threshold(cw, "北京", "上海"), 1300.0)
        self.assertEqual(leg_threshold(cw, "BJS", "SHA"), 1300.0)
        self.assertEqual(leg_threshold(cw, "上海", "北京"), 1000.0)

    def test_02_leg_threshold_fallback_and_junk(self):
        cw = _cw()
        cw["route_thresholds"] = {"北京>上海": "abc", "x": 5,
                                  "重庆>上海": -3}
        self.assertEqual(leg_threshold(cw, "北京", "上海"), 1000.0)
        self.assertEqual(leg_threshold(cw, "重庆", "上海"), 1000.0)
        cw["threshold_total"] = 0
        self.assertEqual(leg_threshold(cw, "北京", "上海"), 0.0)

    def test_03_evaluate_alert_per_leg(self):
        hits = evaluate_alert(_hist(), _cw())
        by = {h["route_id"]: h for h in hits}
        self.assertIn("patrol-北京-上海", by)
        self.assertEqual(by["patrol-北京-上海"]["threshold"], 1300.0)
        self.assertNotIn("patrol-重庆-上海", by)

    def test_04_config_validation_cleans_rts(self):
        body = webui.load_config(webui.CONFIG_PATH)
        body["cabin_watch"] = {
            "enabled": True, "threshold_total": 1000,
            "route_thresholds": {"北京>上海": 1300, "bad": "x",
                                 "neg>neg": -1, "nodelim": 5},
        }
        out = webui._validate_config(copy.deepcopy(body),
                                     copy.deepcopy(body))
        rts = out["cabin_watch"]["route_thresholds"]
        self.assertEqual(rts, {"北京>上海": 1300.0})

    def test_05_load_config_keeps_rts(self):
        cfg = {"cabin_watch": {
            "enabled": True, "threshold_total": 1000,
            "route_thresholds": {"BJS>SHA": 1350},
        }}
        cw = load_config(cfg)
        self.assertEqual(cw["route_thresholds"], {"BJS>SHA": 1350})
        self.assertEqual(leg_threshold(cw, "北京", "上海"), 1350.0)

    def test_06_api_cabin_stamps_threshold(self):
        src = open("webui.py", encoding="utf-8").read()
        self.assertIn('g["threshold"] = cw_leg_threshold(', src)
        self.assertIn('b["threshold"] = cw_leg_threshold(', src)
        js = open("webui/static/app.js", encoding="utf-8").read()
        self.assertIn("g.threshold != null ? g.threshold", js)
        self.assertIn('阈值 " + fmtCny(b.threshold)', js)
        jsx = open("web/src/components/CabinCard.jsx",
                   encoding="utf-8").read()
        self.assertIn("route_thresholds", jsx)
        self.assertIn("r.threshold || cw.threshold_total", jsx)
        idx = open("webui/templates/index.html",
                   encoding="utf-8").read()
        self.assertIn("style.css?v=33", idx)
        self.assertIn("app.js?v=33", idx)
        self.assertIn("v1.25</span>", idx)

    def test_07_version_bump(self):
        from core.version import CODE_VERSION
        self.assertEqual(CODE_VERSION, "1.25")


if __name__ == "__main__":
    unittest.main(verbosity=2)
