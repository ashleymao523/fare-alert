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
    record_alert_candidate, history_board,
    patrol_legs, absorb_point_cabin,
)


class CabinMonitorTests(unittest.TestCase):
    def test_defaults_merge(self):
        cw = load_config({"cabin_watch": {"enabled": True,
                                          "threshold_total": 990}})
        self.assertTrue(cw["enabled"])
        self.assertEqual(cw["threshold_total"], 990)
        self.assertEqual(cw["default_to_city"], "杭州")  # default kept

    def test_absorb_point_cabin_groups_and_filters(self):
        cw = load_config({"cabin_watch": {"enabled": True}})
        now = 1789500000.0
        cache = {
            "beijing-hangzhou": {
                "2026-09-20": {"total": 1800.0, "cabin": "business",
                               "from_city": "北京", "to_city": "杭州",
                               "flight_no": "CA1852",
                               "dep_time": "08:30", "arr_time": "11:05",
                               "ts": now - 60},
                "2026-09-21": {"total": 900.0, "cabin": "",
                               "from_city": "北京", "to_city": "杭州",
                               "ts": now - 60},
                "2026-09-22": {"total": 1700.0, "cabin": "business",
                               "from_city": "北京", "to_city": "杭州",
                               "ts": now - 49 * 3600},   # stale
            },
            "chongqing-hangzhou": {
                "2026-09-27": {"total": 2100.0, "cabin": "business",
                               "from_city": "重庆", "to_city": "杭州",
                               "ts": now - 60},
            },
        }
        groups = absorb_point_cabin(cache, cw, now=now)
        self.assertEqual(set(groups), {"leg-北京-杭州",
                                       "leg-重庆-杭州"})
        rows = groups["leg-北京-杭州"]["rows"]
        self.assertEqual(len(rows), 1)                 # economy+stale out
        self.assertEqual(rows[0]["total"], 1800.0)
        self.assertEqual(rows[0]["cabin"], "business")
        self.assertEqual(groups["leg-重庆-杭州"]["leg"]["from_city"],
                         "重庆")

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

    def test_history_board_low_with_date_latest_and_gap(self):
        h = {"routes": {}}
        record_low(h, "ckg-hgh", "重庆", "杭州", "business",
                   "2026-10-03", 3200)
        record_low(h, "ckg-hgh", "重庆", "杭州", "business",
                   "2026-10-05", 2900)   # all-time low
        record_low(h, "ckg-hgh", "重庆", "杭州", "business",
                   "2026-10-07", 3350)   # latest bounce
        rows = history_board(h)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["low"], 2900)
        self.assertEqual(row["low_date"], "2026-10-05")
        self.assertEqual(row["latest"], 3350)
        self.assertEqual(row["latest_date"], "2026-10-07")
        self.assertEqual(row["gap"], 450)
        self.assertEqual(row["samples"], 3)

    def test_history_board_sorted_by_low_skips_empty_legs(self):
        h = {"routes": {}}
        record_low(h, "a", "北京", "杭州", "business", "2026-10-01", 4000)
        record_low(h, "b", "重庆", "杭州", "business", "2026-10-02", 2900)
        h["routes"]["empty"] = {"from_city": "西安", "to_city": "杭州",
                                "obs": [], "lowest": None}
        rows = history_board(h)
        self.assertEqual([r["route_id"] for r in rows], ["b", "a"])
        self.assertEqual(rows[0]["from_city"], "重庆")

    def test_history_board_empty_history_safe(self):
        self.assertEqual(history_board({}), [])
        self.assertEqual(history_board({"routes": {}}), [])


class PatrolLegsTests(unittest.TestCase):
    """v0.66: standalone watch legs = watch_from x to, minus pairs
    configured routes already feed (direct or mirror)."""

    def test_cross_product_sorted_and_dedup(self):
        cw = {"enabled": True, "to_cities": ["杭州", "宁波"],
              "watch_from_cities": ["重庆", "北京", "重庆"]}
        legs = patrol_legs(cw, [])
        self.assertEqual(legs, [
            {"from_city": "北京", "to_city": "宁波"},
            {"from_city": "北京", "to_city": "杭州"},
            {"from_city": "重庆", "to_city": "宁波"},
            {"from_city": "重庆", "to_city": "杭州"},
        ])

    def test_route_covered_pairs_excluded(self):
        # 杭州->重庆 route mirrors 重庆->杭州; 成都->杭州 is direct
        cw = {"enabled": True, "to_cities": ["杭州"],
              "watch_from_cities": ["重庆", "成都", "北京"]}
        routes = [{"from_city": "杭州", "to_city": "重庆"},
                  {"from_city": "成都", "to_city": "杭州"}]
        self.assertEqual(patrol_legs(cw, routes),
                         [{"from_city": "北京", "to_city": "杭州"}])

    def test_disabled_or_empty_inputs(self):
        self.assertEqual(patrol_legs(
            {"enabled": False, "to_cities": ["杭州"],
             "watch_from_cities": ["重庆"]}, []), [])
        self.assertEqual(patrol_legs(
            {"enabled": True, "to_cities": ["杭州"],
             "watch_from_cities": []}, []), [])
        self.assertEqual(patrol_legs(
            {"enabled": True, "to_cities": [],
             "watch_from_cities": ["重庆"]}, []), [])

    def test_same_city_pair_drops(self):
        cw = {"enabled": True, "to_cities": ["杭州", "北京"],
              "watch_from_cities": ["杭州", "北京"]}
        self.assertEqual(patrol_legs(cw, []), [
            {"from_city": "北京", "to_city": "杭州"},
            {"from_city": "杭州", "to_city": "北京"},
        ])

    def test_default_config_has_refresh_minutes(self):
        self.assertEqual(default_config()["refresh_minutes"], 30)
        cw = load_config({"cabin_watch": {"refresh_minutes": 15}})
        self.assertEqual(cw["refresh_minutes"], 15)


if __name__ == "__main__":
    unittest.main()
