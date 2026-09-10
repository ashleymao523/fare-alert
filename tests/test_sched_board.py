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

    def test_exact_dow_city_mismatch_falls_to_cross(self):
        # exact dow exists but for another city pair -> borrow cross-dow
        db = self._db({
            "3": {"dep": "09:00", "arr": "", "from": "北京", "to": "重庆"},
            "1": {"dep": "07:55", "arr": "", "from": "杭州", "to": "重庆"},
        })
        hit = sb.board_lookup_x(db, "GJ8888", "2026-09-10", "杭州", "重庆")
        self.assertEqual(hit[1], False)
        self.assertEqual(hit[0]["dep"], "07:55")

    def test_bad_date_returns_none(self):
        db = self._db({"2": {"dep": "07:55", "arr": "",
                             "from": "杭州", "to": "重庆"}})
        self.assertIsNone(sb.board_lookup_x(db, "GJ8888", "not-a-date",
                                            "杭州", "重庆"))


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


if __name__ == "__main__":
    unittest.main(verbosity=1)
