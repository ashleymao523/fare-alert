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
    load_config, record_low, route_qualifies, cabin_leg,
    record_alert_candidate,
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

    def test_record_low_tags_fresh_all_time_low(self):
        # v0.52: first sample is never a record (bootstrap must not
        # alert); an undercut is, and carries the previous low
        h = {"routes": {}}
        e1 = record_low(h, "cq-hgh", "重庆", "杭州", "business",
                        "2026-10-01", 1800)
        self.assertFalse(e1.get("record"))
        e2 = record_low(h, "cq-hgh", "重庆", "杭州", "business",
                        "2026-10-02", 1650)
        self.assertTrue(e2["record"])
        self.assertEqual(e2["record_prev"], 1800)
        e3 = record_low(h, "cq-hgh", "重庆", "杭州", "business",
                        "2026-10-03", 1700)
        self.assertFalse(e3.get("record"))  # above the 1650 low

    def test_record_low_same_day_replacement_recomputes(self):
        h = {"routes": {}}
        record_low(h, "cq-hgh", "重庆", "杭州", "business", "2026-10-01", 1800)
        record_low(h, "cq-hgh", "重庆", "杭州", "business", "2026-10-02", 1600)
        # re-observing day-01 higher than its old sample: not a record
        e = record_low(h, "cq-hgh", "重庆", "杭州", "business",
                       "2026-10-01", 1750)
        self.assertFalse(e.get("record"))
        # dropping day-01 under the 1600 low IS a record
        e2 = record_low(h, "cq-hgh", "重庆", "杭州", "business",
                        "2026-10-01", 1550)
        self.assertTrue(e2["record"])
        self.assertEqual(e2["record_prev"], 1600)

    def test_record_alert_candidate_dedup(self):
        # never alerted -> any fresh record alerts
        c = record_alert_candidate([{"date": "2026-10-02", "price": 1650,
                                     "record": True, "record_prev": 1800}],
                                   None)
        self.assertEqual(c["price"], 1650)
        # already alerted 1650: same price never re-alerts, only lower
        self.assertIsNone(record_alert_candidate(
            [{"date": "2026-10-03", "price": 1650, "record": True}],
            1650))
        c2 = record_alert_candidate(
            [{"date": "2026-10-03", "price": 1500, "record": True}],
            1650)
        self.assertEqual(c2["price"], 1500)
        # picks the best of several fresh records
        c3 = record_alert_candidate(
            [{"price": 1600, "record": True}, {"price": 1499, "record": True}],
            1650)
        self.assertEqual(c3["price"], 1499)
        # empty / garbage-safe
        self.assertIsNone(record_alert_candidate([], None))
        self.assertIsNone(record_alert_candidate(
            [{"price": "n/a", "record": True}], None))

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

    def test_cabin_leg_direct_and_mirror(self):
        # v0.50: a route whose to_city is watched feeds itself (direct)
        cw = load_config({"cabin_watch": {"enabled": True}})
        leg = cabin_leg({"from_city": "重庆", "to_city": "杭州"}, cw)
        self.assertEqual(leg, {"mode": "direct", "from_city": "重庆",
                               "to_city": "杭州"})
        # ... while a HGH->CKG route auto-derives the mirrored CKG->HGH
        leg2 = cabin_leg({"from_city": "杭州", "to_city": "重庆"}, cw)
        self.assertEqual(leg2, {"mode": "mirror", "from_city": "重庆",
                                "to_city": "杭州"})
        # neither end watched -> no leg
        self.assertIsNone(
            cabin_leg({"from_city": "北京", "to_city": "成都"}, cw))
        # disabled -> no leg even when matched
        cw_off = load_config({"cabin_watch": {"enabled": False}})
        self.assertIsNone(cabin_leg({"from_city": "杭州", "to_city": "重庆"},
                                    cw_off))

    def test_cabin_leg_mirror_watch_from_narrows_by_leg_departure(self):
        # watch_from_cities filters by the WATCH leg's departure city:
        # a mirrored CKG->HGH leg survives only when 重庆 is watched-from
        cw = load_config({"cabin_watch": {
            "enabled": True, "watch_from_cities": ["重庆"]}})
        leg = cabin_leg({"from_city": "杭州", "to_city": "重庆"}, cw)
        self.assertEqual(leg["mode"], "mirror")
        cw2 = load_config({"cabin_watch": {
            "enabled": True, "watch_from_cities": ["成都"]}})
        self.assertIsNone(
            cabin_leg({"from_city": "杭州", "to_city": "重庆"}, cw2))

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
