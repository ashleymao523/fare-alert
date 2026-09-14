# -*- coding: utf-8 -*-
"""M4 weekly report: stats recomputable + push switchable (DoD)."""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.history import append_history, load_history
from core.weekly import (PUSH_INTERVAL, attach_global_best, build_weekly,
                        global_best, global_best_line, mark_failed,
                        mark_pushed, push_text, should_push, week_highlights)


def _snap(cheapest_total, days_below=0):
    return {"routes": [{
        "id": "r1", "from_city": "杭州", "to_city": "重庆",
        "threshold_total": 600, "days_below": days_below,
        "deals": [
            {"date": "2026-10-0" + str(i), "total_price": p,
             "source": "qunar-calendar"}
            for i, p in enumerate([999, cheapest_total, 1200], start=1)
        ] + [
            {"date": "2026-10-09", "total_price": 100,
             "source": "interp"},
        ],
    }]}


class TestHistory(unittest.TestCase):
    def test_append_and_overwrite_same_day(self):
        path = os.path.join(os.path.dirname(__file__), "_hist_test.json")
        if os.path.exists(path):
            os.remove(path)
        try:
            n = append_history(_snap(430, 3), path)
            self.assertEqual(n, 1)
            append_history(_snap(450, 4), path)  # same-day rerun overwrites
            today = load_history(path)["days"]
            self.assertEqual(len(today), 1)
            m = list(today.values())[0]["routes"]["r1"]
            self.assertEqual(m["cheapest_total"], 450)
            self.assertEqual(m["days_below"], 4)
            self.assertEqual(m["n_deals"], 3)  # interp excluded
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestWeekly(unittest.TestCase):
    def _hist_path(self, week, prev=None):
        path = os.path.join(os.path.dirname(__file__), "_wk_test.json")
        days = {}
        for i, v in enumerate(prev or []):
            day = "2026-08-{:02d}".format(10 + i)
            days[day] = {"routes": {"r1": {
                "from_city": "杭州", "to_city": "重庆", "threshold": 600,
                "cheapest_total": v, "avg_total": v + 20, "days_below": 1,
                "best_date": "2026-09-01", "n_deals": 30}}}
        for i, v in enumerate(week):
            day = "2026-09-{:02d}".format(1 + i)
            days[day] = {"routes": {"r1": {
                "from_city": "杭州", "to_city": "重庆", "threshold": 600,
                "cheapest_total": v, "avg_total": v + 20, "days_below": 2,
                "best_date": "2026-10-0" + str(1 + i), "n_deals": 30}}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"days": days}, f, ensure_ascii=False)
        return path

    def test_stats_recomputable_and_text(self):
        path = self._hist_path(week=[500, 480, 460, 470, 440, 465, 455],
                               prev=[520, 510, 505, 515, 498, 530, 512])
        try:
            rep = build_weekly(path)
            self.assertTrue(rep["ok"])
            r = rep["routes"][0]
            week_vals = [500, 480, 460, 470, 440, 465, 455]
            prev_vals = [520, 510, 505, 515, 498, 530, 512]
            self.assertEqual(r["week"]["min"], min(week_vals))
            self.assertAlmostEqual(r["week"]["avg"],
                                   round(sum(week_vals) / 7, 1))
            self.assertEqual(r["prev"]["min"], min(prev_vals))
            self.assertIn("440", r["text"])
            self.assertIn("498", r["text"])
            self.assertIn("阈值", r["text"])
            self.assertIn("杭州→重庆", r["text"])
        finally:
            os.remove(path)

    def test_no_prev_week_tolerated(self):
        path = self._hist_path(week=[500, 480])
        try:
            rep = build_weekly(path)
            self.assertIsNone(rep["routes"][0]["prev"])
            self.assertIn("上周暂无数据", rep["routes"][0]["text"])
        finally:
            os.remove(path)

    def test_zero_prev_min_no_crash(self):
        path = self._hist_path(week=[500, 480], prev=[0, 510, 505, 515, 498, 530, 512])
        try:
            rep = build_weekly(path)  # must not raise ZeroDivisionError
            r = rep["routes"][0]
            self.assertEqual(r["prev"]["min"], 0)
            self.assertIn("贵 ¥480", r["text"])  # delta shown, no pct
            self.assertNotIn("Infinity", r["text"])
        finally:
            os.remove(path)

    def test_push_switch_and_cooldown(self):
        path = os.path.join(os.path.dirname(__file__), "_wkpush_test.json")
        if os.path.exists(path):
            os.remove(path)
        try:
            self.assertFalse(should_push({"push": {}}, path))
            cfg = {"push": {"weekly_enabled": True}}
            self.assertTrue(should_push(cfg, path))
            mark_pushed(path)
            self.assertFalse(should_push(cfg, path))
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            doc["ts"] = time.time() - PUSH_INTERVAL - 10
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            self.assertTrue(should_push(cfg, path))
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_failed_push_backoff_no_storm(self):
        path = os.path.join(os.path.dirname(__file__), "_wkfail_test.json")
        if os.path.exists(path):
            os.remove(path)
        try:
            cfg = {"push": {"weekly_enabled": True}}
            self.assertTrue(should_push(cfg, path))
            mark_failed(path)
            self.assertFalse(should_push(cfg, path))  # inside 6h backoff
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            doc["retry_after"] = time.time() - 1
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            self.assertTrue(should_push(cfg, path))  # backoff elapsed
            mark_pushed(path)  # success clears backoff state
            self.assertFalse(should_push(cfg, path))
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestWeekHighlights(unittest.TestCase):
    """v0.57: week_highlights board recomputed from the archive."""

    @staticmethod
    def _m(v, days_below=0, threshold=600):
        return {"from_city": "杭州", "to_city": "重庆", "threshold": threshold,
                "cheapest_total": v, "avg_total": v + 20,
                "days_below": days_below, "best_date": "2026-10-01",
                "n_deals": 30}

    @staticmethod
    def _path(prev, week, days_below=0):
        path = os.path.join(os.path.dirname(__file__), "_wkhl_test.json")
        days = {}
        for i, v in enumerate(prev):
            day = "2026-08-{:02d}".format(10 + i)
            days[day] = {"routes": {"r1": TestWeekHighlights._m(v)}}
        for i, v in enumerate(week):
            day = "2026-09-{:02d}".format(1 + i)
            days[day] = {"routes": {
                "r1": TestWeekHighlights._m(v, days_below=days_below)}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"days": days}, f, ensure_ascii=False)
        return path

    def test_board_drop_sharp_and_below(self):
        path = self._path(prev=[650] * 7,
                          week=[520, 510, 500, 490, 480, 470, 380],
                          days_below=3)
        try:
            rep = build_weekly(path)
            hl = rep["highlights"]
            self.assertEqual(hl["biggest_drop"]["delta"], -270.0)
            self.assertEqual(hl["biggest_drop"]["pct"], -41.5)
            self.assertEqual(len(hl["sharp_drops"]), 1)
            self.assertEqual(hl["sharp_drops"][0]["delta"], -90.0)
            self.assertEqual(hl["below_threshold"][0]["days_below"], 3)
            self.assertIn("最大降幅", hl["text"])
            self.assertIn("1 次骤降", hl["text"])
        finally:
            os.remove(path)

    def test_calm_week_all_empty(self):
        path = self._path(prev=[500] * 7, week=[500] * 7)
        try:
            hl = build_weekly(path)["highlights"]
            self.assertIsNone(hl["biggest_drop"])
            self.assertEqual(hl["sharp_drops"], [])
            self.assertEqual(hl["below_threshold"], [])
            self.assertIn("平稳", hl["text"])
        finally:
            os.remove(path)

    def test_no_prev_week_and_mild_drop_not_sharp(self):
        path = self._path(prev=[],
                          week=[500, 495, 480, 470, 500, 480, 475],
                          days_below=2)
        try:
            hl = build_weekly(path)["highlights"]
            self.assertIsNone(hl["biggest_drop"])    # no prev week
            self.assertEqual(hl["sharp_drops"], [])  # -4% fails 15% gate
            self.assertEqual(hl["below_threshold"][0]["days_below"], 2)
        finally:
            os.remove(path)

    def test_empty_history_safe(self):
        hl = week_highlights({"days": {}})
        self.assertIsNone(hl["biggest_drop"])
        self.assertEqual(hl["sharp_drops"], [])
        self.assertEqual(hl["below_threshold"], [])
        self.assertIn("平稳", hl["text"])


class TestPushText(unittest.TestCase):
    """v0.58: the pushed body leads with the highlights line."""

    def test_highlights_line_under_head(self):
        rep = {"text": "📊 价格周报（09-01~09-07）\n杭州→重庆：本周最低 ¥440。",
               "highlights": {"text": "⭐ 本周值得关注：最大降幅 杭州→重庆。"}}
        out = push_text(rep)
        lines = out.split("\n")
        self.assertTrue(lines[0].startswith("📊"))
        self.assertEqual(lines[1], "⭐ 本周值得关注：最大降幅 杭州→重庆。")
        self.assertIn("杭州→重庆：本周最低", out)

    def test_calm_week_still_announced(self):
        rep = {"text": "📊 价格周报（09-01~09-07）\n杭州→重庆：本周最低 ¥440。",
               "highlights": {"text": "本周价格平稳：无破阈值路线、无骤降。"}}
        out = push_text(rep)
        self.assertIn("本周价格平稳", out.split("\n")[1])

    def test_no_highlights_passthrough(self):
        rep = {"text": "📊 价格周报\n正文"}
        self.assertEqual(push_text(rep), "📊 价格周报\n正文")

    def test_no_head_prepends(self):
        rep = {"text": "暂无历史数据",
               "highlights": {"text": "本周价格平稳。"}}
        out = push_text(rep)
        self.assertTrue(out.startswith("本周价格平稳。"))

    def test_build_weekly_exposes_push_text(self):
        path = TestWeekHighlights._path(
            prev=[650] * 7, week=[520, 380, 500, 490, 480, 470, 460])
        try:
            rep = build_weekly(path)
            self.assertIn("本周值得关注", rep["push_text"])
            self.assertIn("价格周报", rep["push_text"])
        finally:
            os.remove(path)


class TestGlobalBest(unittest.TestCase):
    SNAP = {
        "routes": [
            {"id": "a", "from_city": "杭州", "to_city": "重庆",
             "threshold_total": 500,
             "deals": [{"date": "2026-09-20", "total_price": 380,
                        "dep_time": "19:45", "arr_time": "22:25"}]},
            {"id": "b", "from_city": "杭州", "to_city": "成都",
             "threshold_total": 900,
             "deals": [{"date": "2026-09-22", "total_price": 700,
                        "dep_time": "06:35", "arr_time": "09:10"}]},
        ]
    }

    def test_picks_min_ratio_with_times(self):
        gb = global_best(self.SNAP)
        self.assertEqual(gb["route_id"], "a")   # 380/500 beats 700/900
        self.assertEqual(gb["price"], 380)
        self.assertEqual(gb["dep_time"], "19:45")
        self.assertEqual(gb["savings"], 120)

    def test_skips_bad_thresholds_and_prices(self):
        snap = {"routes": [
            {"id": "x", "threshold_total": 0, "deals": [
                {"date": "d", "total_price": 100}]},
            {"id": "y", "threshold_total": 500, "deals": [
                {"date": "d", "total_price": None},
                {"date": "d2", "total_price": "abc"}]},
        ]}
        self.assertIsNone(global_best(snap))
        self.assertIsNone(global_best({}))
        self.assertIsNone(global_best(None))

    def test_line_format_under_and_over_threshold(self):
        under = global_best_line(global_best(self.SNAP))
        self.assertIn("🏆 全局最优 杭州→重庆 09-20 ¥380", under)
        self.assertIn("(19:45-22:25)", under)
        self.assertIn("比心理价低¥120", under)
        over = dict(global_best(self.SNAP), savings=-30)
        self.assertIn("距心理价¥30", global_best_line(over))

    def test_attach_inserts_under_head_no_dup(self):
        report = {"push_text": "📊 价格周报（09-08~09-14）\n正文"}
        out = attach_global_best(report, self.SNAP)
        self.assertIn("🏆 全局最优", out["push_text"].split("\n")[1])
        self.assertIn("global_best", out)
        again = attach_global_best(dict(out), self.SNAP)
        self.assertEqual(again["push_text"].count("全局最优"), 1)

    def test_attach_safe_without_best_or_text(self):
        bare = {"push_text": "只有正文没有表头"}
        self.assertEqual(attach_global_best(bare, {}).get("push_text"),
                         "只有正文没有表头")
        self.assertIsNone(
            attach_global_best({}, self.SNAP).get("global_best"))


if __name__ == "__main__":
    unittest.main()
