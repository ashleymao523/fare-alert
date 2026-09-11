# -*- coding: utf-8 -*-
"""v0.18 airport-board time library: parse -> db merge -> lookup (DoD)."""
import copy
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import sched_board as sb

FIX_PATH = os.path.join(os.path.dirname(__file__), "fixtures",
                        "hgh_board_sample.json")


def _fixture():
    with open(FIX_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestParse(unittest.TestCase):
    def test_leave_entry_dep_only(self):
        ent = sb._entry_from_leave({
            "hbh": "gj 8888", "jhsj": "2026-09-10 07:55:00",
            "chinese_sfcs": "杭州/萧山", "chinese_mdcs": "重庆/江北",
            "chinese_hs": "长龙航空", "jxzs": "A320"})
        self.assertEqual(ent["dep"], "07:55")
        self.assertEqual(ent["arr"], "")
        self.assertEqual(ent["from"], "杭州")
        self.assertEqual(ent["to"], "重庆")
        self.assertEqual(ent["src"], "airport-board")

    def test_arrive_entry_both_times(self):
        ent = sb._entry_from_arrive({
            "hbh": "GJ8889", "preschtime": "2026-09-10 06:20:00",
            "jhsj": "2026-09-10 10:30:00",
            "chinese_sfcs": "重庆/江北", "chinese_mdcs": "杭州/萧山"})
        self.assertEqual(ent["dep"], "06:20")
        self.assertEqual(ent["arr"], "10:30")
        self.assertEqual(ent["from"], "重庆")
        self.assertEqual(ent["to"], "杭州")

    def test_row_without_hbh_dropped(self):
        self.assertIsNone(sb._entry_from_leave({"jhsj": "2026-09-10 07:55:00"}))


class TestDbAndLookup(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sb_test_")
        self.addCleanup(shutil.rmtree, self.dir, True)
        fix = _fixture()
        patcher = mock.patch.object(
            sb, "fetch_board",
            side_effect=lambda s, n, kind, d, force=False: (fix[kind], False))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db = sb.update_sched_db(None, {}, self.dir)
        self.today = dt.date.today()
        self.today_iso = self.today.isoformat()
        self.dow = str(self.today.weekday())

    def test_db_built_for_today_dow(self):
        self.assertIn(self.dow, self.db["flights"]["GJ8888"]["dows"])
        self.assertGreater(self.db["updated"], 0)

    def test_codeshare_indexed_under_both_numbers(self):
        for no in ("3U8887", "GJ5321"):
            self.assertIn(no, self.db["flights"])

    def test_arrive_two_times_beat_leave_dep_only(self):
        ent = self.db["flights"]["GJ8889"]["dows"][self.dow]
        self.assertEqual(ent["dep"], "06:20")
        self.assertEqual(ent["arr"], "10:30")

    def test_lookup_hit_dep_only(self):
        ent = sb.board_lookup(self.db, "gj8888 ", self.today_iso, "杭州", "重庆")
        self.assertEqual(ent["dep"], "07:55")
        self.assertEqual(ent["arr"], "")

    def test_lookup_hit_both_times(self):
        ent = sb.board_lookup(self.db, "GJ8889", self.today_iso, "重庆", "杭州")
        self.assertEqual((ent["dep"], ent["arr"]), ("06:20", "10:30"))

    def test_lookup_city_mismatch(self):
        self.assertIsNone(sb.board_lookup(self.db, "GJ8888", self.today_iso,
                                          "北京", "重庆"))

    def test_lookup_wrong_dow(self):
        other = (self.today + dt.timedelta(days=1)).isoformat()
        self.assertIsNone(sb.board_lookup(self.db, "GJ8888", other,
                                          "杭州", "重庆"))

    def test_lookup_unknown_flight(self):
        self.assertIsNone(sb.board_lookup(self.db, "CA9999", self.today_iso,
                                          "杭州", "重庆"))

    def test_later_leave_cannot_erase_arrive_time(self):
        fix2 = copy.deepcopy(_fixture())
        for row in fix2["arrive"]:
            if row["hbh"] == "GJ8889":
                row["preschtime"] = ""
        with mock.patch.object(
                sb, "fetch_board",
                side_effect=lambda s, n, kind, d, force=False: (fix2[kind], False)):
            db2 = sb.update_sched_db(None, {}, self.dir)
        ent = db2["flights"]["GJ8889"]["dows"][self.dow]
        self.assertEqual(ent["arr"], "10:30")
        self.assertEqual(ent["dep"], "06:20")  # dep must survive too


class TestLookupX(unittest.TestCase):
    """v0.19 board_lookup_x: exact dow first, then cross-dow borrow."""

    def _db(self, dows):
        return {"updated": 0, "flights": {"GJ8888": {"dows": dows}}}

    def test_exact_dow_hit(self):
        db = self._db({"2": {"dep": "07:55", "arr": "",
                             "from": "杭州", "to": "重庆"}})
        hit = sb.board_lookup_x(db, "GJ8888", "2026-09-09", "杭州", "重庆")
        self.assertEqual(hit[1], True)
        self.assertEqual(hit[0]["dep"], "07:55")

    def test_cross_dow_borrow(self):
        # 2026-09-10 is dow 3; db only has dow 2 -> borrow as reference
        db = self._db({"2": {"dep": "07:55", "arr": "",
                             "from": "杭州", "to": "重庆"}})
        hit = sb.board_lookup_x(db, "GJ8888", "2026-09-10", "杭州", "重庆")
        self.assertEqual(hit[1], False)
        self.assertEqual(hit[0]["dep"], "07:55")

    def test_cross_dow_city_mismatch_returns_none(self):
        db = self._db({"2": {"dep": "07:55", "arr": "",
                             "from": "杭州", "to": "重庆"}})
        self.assertIsNone(sb.board_lookup_x(db, "GJ8888", "2026-09-10",
                                            "北京", "重庆"))

    def test_cross_dow_prefers_dual_time_entry(self):
        db = self._db({
            "1": {"dep": "07:55", "arr": "", "from": "杭州", "to": "重庆"},
            "3": {"dep": "08:10", "arr": "10:35", "from": "杭州", "to": "重庆"},
        })
        hit = sb.board_lookup_x(db, "GJ8888", "2026-09-09", "杭州", "重庆")
        self.assertEqual(hit[1], False)
        self.assertEqual((hit[0]["dep"], hit[0]["arr"]), ("08:10", "10:35"))

    def test_unknown_flight_returns_none(self):
        self.assertIsNone(sb.board_lookup_x(self._db({}), "CA9999",
                                            "2026-09-10", "杭州", "重庆"))

    def test_exact_dow_stopover_city_still_exact(self):
        # v0.22: 板按号+dow+机场唯一定位一班, 终点城市不同多为经停
        # 最终点记录差异(杭州->克拉玛依 实际经停郑州), 仍算精确命中
        db = self._db({
            "3": {"dep": "09:00", "arr": "", "from": "北京", "to": "重庆"},
            "1": {"dep": "07:55", "arr": "", "from": "杭州", "to": "重庆"},
        })
        hit = sb.board_lookup_x(db, "GJ8888", "2026-09-10", "杭州", "重庆")
        self.assertEqual(hit[1], True)
        self.assertEqual(hit[0]["dep"], "09:00")

    def test_bad_date_returns_none(self):
        db = self._db({"2": {"dep": "07:55", "arr": "",
                             "from": "杭州", "to": "重庆"}})
        self.assertIsNone(sb.board_lookup_x(db, "GJ8888", "not-a-date",
                                            "杭州", "重庆"))

    def test_cross_dow_stopover_final_city_borrows(self):
        # v0.22: cross-dow borrow also allows stopover legs when the
        # departure side matches (杭州->克拉玛依 actually stops at 郑州)
        db = self._db({"2": {"dep": "06:35", "arr": "",
                             "from": "杭州", "to": "克拉玛依"}})
        hit = sb.board_lookup_x(db, "GJ8888", "2026-09-10", "杭州", "郑州")
        self.assertIsNotNone(hit)
        self.assertEqual(hit[1], False)
        self.assertEqual(hit[0]["dep"], "06:35")

    def test_cross_dow_origin_mismatch_rejected(self):
        # v0.22: neither side matches -> tier3, refuse to borrow cross-dow
        db = self._db({"2": {"dep": "06:35", "arr": "",
                             "from": "北京", "to": "克拉玛依"}})
        self.assertIsNone(sb.board_lookup_x(db, "GJ8888", "2026-09-10",
                                            "杭州", "郑州"))


class _FakeResp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _CountingSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, url, **kw):
        self.calls += 1
        return _FakeResp(self.payload)


def _age_cache(path, secs=None):
    with open(path, encoding="utf-8") as f:
        ent = json.load(f)
    ent["ts"] = time.time() - (secs if secs is not None else sb.BOARD_TTL + 10)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ent, f)


class TestFetchGuardrails(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sb_guard_")
        self.addCleanup(shutil.rmtree, self.dir, True)
        fix = _fixture()
        self.sess = _CountingSession({"flag": 1, "data": fix["leave"]})
        self.cache = os.path.join(
            self.dir, "board_leave_%s.json" % dt.date.today().isoformat())

    def test_daily_hard_cap_serves_stale_cache(self):
        _, cached = sb.fetch_board(self.sess, {}, "leave", self.dir)
        self.assertFalse(cached)
        self.assertEqual(self.sess.calls, 1)
        _age_cache(self.cache)
        sb.fetch_board(self.sess, {}, "leave", self.dir)
        self.assertEqual(self.sess.calls, 2)
        _age_cache(self.cache)
        rows, cached = sb.fetch_board(self.sess, {}, "leave", self.dir)
        self.assertTrue(cached)  # 3rd request blocked by daily cap
        self.assertEqual(self.sess.calls, 2)
        self.assertTrue(rows)

    def test_force_bypasses_daily_cap(self):
        sb.fetch_board(self.sess, {}, "leave", self.dir)
        _age_cache(self.cache)
        sb.fetch_board(self.sess, {}, "leave", self.dir)
        _age_cache(self.cache)
        _, cached = sb.fetch_board(self.sess, {}, "leave", self.dir, force=True)
        self.assertFalse(cached)
        self.assertEqual(self.sess.calls, 3)

    def test_corrupt_db_backed_up_and_rebuilt(self):
        dbp = os.path.join(self.dir, sb.DB_NAME)
        with open(dbp, "w", encoding="utf-8") as f:
            f.write("{ half-written not json")
        fix = _fixture()
        with mock.patch.object(
                sb, "fetch_board",
                side_effect=lambda s, n, kind, d, force=False: (fix[kind], False)):
            db = sb.update_sched_db(None, {}, self.dir)
        backups = [x for x in os.listdir(self.dir)
                   if x.startswith(sb.DB_NAME + ".corrupt-")]
        self.assertTrue(backups)
        self.assertIn("GJ8888", db["flights"])

    def test_gate_matches_real_config_keys(self):
        # real config.json uses from_city/to_city (review P1 regression guard)
        routes = [
            {"from_city": "成都", "to_city": "郑州"},
            {"from_city": "杭州", "to_city": "重庆", "window_days": 60},
        ]
        self.assertTrue(sb.touches_hangzhou(routes))
        self.assertFalse(sb.touches_hangzhou([{"from_city": "成都",
                                               "to_city": "郑州"}]))
        self.assertTrue(sb.touches_hangzhou(
            [{"from_city": "chengdu", "to_city": "HGH"}]))
        self.assertFalse(sb.touches_hangzhou([]))
        self.assertFalse(sb.touches_hangzhou(None))

    def test_failed_attempts_burn_daily_budget(self):
        class _FailingSession:
            def __init__(self):
                self.calls = 0

            def get(self, url, **kw):
                self.calls += 1
                raise RuntimeError("network down")

        sess = _FailingSession()
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                sb.fetch_board(sess, {}, "leave", self.dir)
        self.assertEqual(sess.calls, 2)
        with self.assertRaises(RuntimeError) as cm:  # capped, no 3rd attempt
            sb.fetch_board(sess, {}, "leave", self.dir)
        self.assertIn("daily fetch cap reached", str(cm.exception))
        self.assertEqual(sess.calls, 2)


class TestSchedStats(unittest.TestCase):
    """v0.20 coverage widget: pure histogram, empty entries never count."""

    def test_empty_db_shape(self):
        st = sb.sched_stats({"updated": 0, "flights": {}})
        self.assertEqual(st["flights"], 0)
        self.assertEqual(st["updated"], 0)
        self.assertEqual(set(st["dows"]), {str(i) for i in range(7)})
        self.assertTrue(all(v == 0 for v in st["dows"].values()))

    def test_histogram_skips_empty_entries(self):
        db = {"updated": 1750000000.5, "flights": {
            "GJ8888": {"dows": {"0": {"dep": "07:30"},
                                 "3": {"dep": "08:10"}}},
            "SC4774": {"dows": {"0": None, "5": {}}},
        }}
        st = sb.sched_stats(db)
        self.assertEqual(st["flights"], 1)      # SC4774 has no real entry
        self.assertEqual(st["dows"]["0"], 1)    # None on dow0 not counted
        self.assertEqual(st["dows"]["3"], 1)
        self.assertEqual(st["dows"]["5"], 0)    # {} not counted
        self.assertEqual(st["dows"]["1"], 0)
        self.assertEqual(st["updated"], 1750000000.5)


class TestRoutePriors(unittest.TestCase):
    def _db(self, *legs):
        flights = {}
        for i, (city, dep, arr) in enumerate(legs):
            flights["T%d" % i] = {"dows": {"3": {
                "dep": dep, "arr": arr, "from": city,
                "to": "杭州"}}}
        return {"updated": 1, "flights": flights}

    def test_prior_median_and_samples(self):
        priors = sb.build_route_priors(self._db(
            ("重庆", "08:00", "10:30"),
            ("重庆", "09:00", "11:35"),
            ("重庆", "10:00", "12:40")))
        self.assertEqual(priors["重庆"]["minutes"], 155)
        self.assertEqual(priors["重庆"]["n"], 3)

    def test_red_eye_wraps_midnight(self):
        priors = sb.build_route_priors(self._db(
            ("乌鲁木齐", "23:30", "04:25"),
            ("乌鲁木齐", "22:00", "03:00"),
            ("乌鲁木齐", "21:00", "01:55")))
        self.assertEqual(priors["乌鲁木齐"]["minutes"], 295)

    def test_garbage_rows_rejected(self):
        # rows outside the 45min..17h window are dropped by the gate
        # (20min row, 12h row, >17h next-day row); the 3 valid ~120min
        # rows still yield a clean prior (median not dragged by garbage).
        priors = sb.build_route_priors(self._db(
            ("哈尔滨", "08:00", "08:20"),
            ("哈尔滨", "08:00", "20:00"),
            ("哈尔滨", "08:00", "02:00"),
            ("哈尔滨", "09:00", "12:00"),
            ("哈尔滨", "10:00", "13:00"),
            ("哈尔滨", "11:00", "14:00")))
        self.assertEqual(priors["哈尔滨"]["minutes"], 180)

    def test_codeshare_rows_deduped(self):
        # one physical flight sold under several codeshare numbers is
        # one sample, not three (v0.25 review P1)
        priors = sb.build_route_priors(self._db(
            ("重庆", "08:00", "10:30"),
            ("重庆", "08:00", "10:30"),
            ("重庆", "08:00", "10:30"),
            ("重庆", "09:00", "11:35"),
            ("重庆", "10:00", "12:40")))
        self.assertEqual(priors["重庆"]["n"], 3)
        self.assertEqual(priors["重庆"]["minutes"], 155)

    def test_stopover_cluster_takes_full_leg(self):
        # stopover rows carry only the last leg (100min); nonstop rows
        # carry the whole trip (290min): biggest-median cluster wins
        priors = sb.build_route_priors(self._db(
            ("阿克苏", "07:00", "08:40"),
            ("阿克苏", "09:00", "10:40"),
            ("阿克苏", "11:00", "12:40"),
            ("阿克苏", "08:00", "12:50"),
            ("阿克苏", "09:30", "14:20"),
            ("阿克苏", "10:00", "14:50")))
        self.assertEqual(priors["阿克苏"]["minutes"], 290)
        self.assertEqual(priors["阿克苏"]["n"], 3)

    def test_stopover_only_city_dropped_by_floor(self):
        # Lhasa has no nonstop from HGH: every row is a stopover and its
        # 150min last-leg cluster is below the great-circle floor (~215min
        # @900km/h+30), so the fake prior is dropped (v0.25.1 review P2)
        priors = sb.build_route_priors(self._db(
            ("拉萨", "07:00", "09:30"),
            ("拉萨", "09:00", "11:30"),
            ("拉萨", "11:00", "13:30")))
        self.assertNotIn("拉萨", priors)

    def test_all_clusters_below_min_samples_dropped(self):
        # two stopover rows + two nonstop rows: no cluster reaches
        # min_samples=3, the city falls back to the geometric estimate
        priors = sb.build_route_priors(self._db(
            ("银川", "07:00", "08:40"),
            ("银川", "09:00", "10:40"),
            ("银川", "08:00", "10:30"),
            ("银川", "09:30", "12:00")))
        self.assertNotIn("银川", priors)

    def test_three_clusters_pick_biggest_median(self):
        priors = sb.build_route_priors(self._db(
            ("兰州", "07:00", "08:40"),
            ("兰州", "09:00", "10:40"),
            ("兰州", "11:00", "12:40"),
            ("兰州", "07:00", "10:20"),
            ("兰州", "09:00", "12:20"),
            ("兰州", "11:00", "14:20"),
            ("兰州", "07:00", "12:50"),
            ("兰州", "09:00", "14:50"),
            ("兰州", "11:00", "16:50")))
        self.assertEqual(priors["兰州"]["minutes"], 350)

    def test_min_samples_gate(self):
        priors = sb.build_route_priors(self._db(("拉萨", "08:00", "10:00")))
        self.assertEqual(priors, {})

    def test_intl_airport_suffix_normalized(self):
        priors = sb.build_route_priors(self._db(
            ("河内机场", "03:50", "06:55"),
            ("河内机场", "04:00", "07:05"),
            ("河内机场", "03:40", "06:45")))
        self.assertIn("河内", priors)

    def test_prefix_lookup_prefers_busiest_airport(self):
        priors = {
            "曼谷素万那普": {"minutes": 240, "n": 12},
            "曼谷廊曼": {"minutes": 230, "n": 2},
        }
        self.assertEqual(sb.prior_minutes_for(priors, "曼谷"), 240)
        self.assertEqual(sb.prior_minutes_for(priors, "重庆"), None)


if __name__ == "__main__":
    unittest.main(verbosity=1)
