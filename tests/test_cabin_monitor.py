# -*- coding: utf-8 -*-
"""v0.42: business-cabin monitor unit tests (pure, no IO)."""
import unittest
from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.cabin_monitor import (
    HISTORY_CAP, cooldown_ok, default_config, evaluate_alert,
    load_config, record_low, route_qualifies,
)


class CabinMonitorTests(unittest.TestCase):
    def test_defaults_merge(self):
        cw = load_config({"cabin_watch": {"enabled": True,
                                          "threshold_total": 990}})
        self.assertTrue(cw["enabled"])
        self.assertEqual(cw["threshold_total"], 990)
        self.assertEqual(cw["default_to_city"], "杭州")  # default kept

    def test_record_low_same_day_replaces(self):
        h = {"routes": {}}
        record_low(h, "cq-hgh", "重庆", "杭州", "business", "2026-10-01", 1800)
        record_low(h, "cq-hgh", "重庆", "杭州", "business", "2026-10-01", 1650)
        obs = h["routes"]["cq-hgh"]["obs"]
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["price"], 1650)
        self.assertEqual(h["routes"]["cq-hgh"]["lowest"], 1650)

    def test_record_low_ring_cap(self):
        h = {"routes": {}}
        for i in range(HISTORY_CAP + 20):
            record_low(h, "r", "A", "杭州", "business",
                       "2026-%02d-%02d" % (i // 28 + 1, i % 28 + 1), 1000 + i)
        self.assertEqual(len(h["routes"]["r"]["obs"]), HISTORY_CAP)
        self.assertEqual(h["routes"]["r"]["lowest"], 1020)  # oldest kept

    def test_route_qualifies_gate(self):
        cw = default_config()
        cw["enabled"] = True
        r_ok = {"from_city": "重庆", "to_city": "杭州"}
        r_to = {"from_city": "杭州", "to_city": "重庆"}
        self.assertTrue(route_qualifies(r_ok, cw))
        self.assertFalse(route_qualifies(r_to, cw))
        cw["watch_from_cities"] = ["成都"]
        self.assertFalse(route_qualifies(r_ok, cw))

    def test_evaluate_alert_threshold(self):
        h = {"routes": {}}
        record_low(h, "cq-hgh", "重庆", "杭州", "business", "2026-10-05", 1400)
        record_low(h, "cd-hgh", "成都", "杭州", "business", "2026-10-06", 2100)
        cw = {"enabled": True, "threshold_total": 1500}
        hits = evaluate_alert(h, cw)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["route_id"], "cq-hgh")
        self.assertEqual(hits[0]["price"], 1400)

    def test_cooldown(self):
        cw = {"cooldown_hours": 12}
        now = datetime(2026, 9, 14, 12)
        self.assertTrue(cooldown_ok(None, cw, now))
        fresh = (now - timedelta(hours=1)).isoformat()
        self.assertFalse(cooldown_ok(fresh, cw, now))
        stale = (now - timedelta(hours=13)).isoformat()
        self.assertTrue(cooldown_ok(stale, cw, now))

    def test_route_qualifies_multi_destinations(self):
        # v0.47: to_cities is a list - any listed destination matches
        cw = default_config()
        cw["enabled"] = True
        cw["to_cities"] = ["杭州", "宁波"]
        self.assertTrue(route_qualifies(
            {"from_city": "重庆", "to_city": "杭州"}, cw))
        self.assertTrue(route_qualifies(
            {"from_city": "重庆", "to_city": "宁波"}, cw))
        self.assertFalse(route_qualifies(
            {"from_city": "杭州", "to_city": "重庆"}, cw))

    def test_legacy_single_destination_derives_list(self):
        # old configs only carrying default_to_city keep working
        cw = load_config({"cabin_watch": {
            "enabled": True, "default_to_city": "宁波"}})
        self.assertEqual(cw["to_cities"], ["宁波"])
        self.assertEqual(cw["default_to_city"], "宁波")
        self.assertTrue(route_qualifies(
            {"from_city": "重庆", "to_city": "宁波"}, cw))
        self.assertFalse(route_qualifies(
            {"from_city": "重庆", "to_city": "杭州"}, cw))

    def test_destination_list_cleaned_and_deduped(self):
        cw = load_config({"cabin_watch": {
            "enabled": True, "to_cities": [" 杭州 ", "", "宁波", "杭州"]}})
        self.assertEqual(cw["to_cities"], ["杭州", "宁波"])
        self.assertEqual(cw["default_to_city"], "杭州")


if __name__ == "__main__":
    unittest.main()
