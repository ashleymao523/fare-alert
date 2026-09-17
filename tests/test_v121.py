# -*- coding: utf-8 -*-
"""v1.21: value-first slot scheduling for the Shanghai board.

The board answers yesterday/today/tomorrow only, so a dow-target
query can ONLY deposit rows dated inside that window. v1.20 ran
fnos in earliest-observation order, which let always-missing
daily flights (MF8561 class, missing all 7 dows) occupy every slot
while fnos whose last missing dow was TODAY (HO1258/HO1260 class)
starved behind them. This round: out-of-window fnos are skipped
(pure budget burn otherwise) and completable fnos lead, fewest
missing first - the leg converges to full time coverage."""
import datetime as dt
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.sh_board import dow_targets, sh_fill


class _Resp:
    def raise_for_status(self):
        return None

    def json(self):
        return {"success": True, "data": {"flightList": "[]"}}


class FakeSession:
    def __init__(self):
        self.calls = 0

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls += 1
        return _Resp()


def _tmp(name):
    p = os.path.join(os.environ.get("TEMP", "."), name)
    shutil.rmtree(p, ignore_errors=True)
    os.makedirs(p, exist_ok=True)
    return p


def _hist2(d1, f1, d2=None, f2=None):
    obs = [{"date": d1, "fno": f1}]
    if d2 and f2:
        obs.append({"date": d2, "fno": f2})
    return {"routes": {"r1": {
        "from_city": "北京", "to_city": "上海", "obs": obs}}}


class TestValueFirst(unittest.TestCase):
    def setUp(self):
        self.today = dt.date.today()
        self.tomorrow = self.today + dt.timedelta(days=1)
        # weekday(today+3) is guaranteed OUTSIDE {today, tomorrow} dows
        self.far = self.today + dt.timedelta(days=3)

    def test_out_of_window_fno_is_skipped(self):
        out = dow_targets(_hist2(self.today.isoformat(), "HO1254",
                                 self.far.isoformat(), "HO1258"),
                          {"flights": {}})
        self.assertEqual([t["fno"] for t in out], ["HO1254"])

    def test_completable_leads_fewest_missing_first(self):
        out = dow_targets(
            _hist2(self.today.isoformat(), "HO1254",
                   self.tomorrow.isoformat(), "HO1258"),
            {"flights": {}})
        self.assertEqual([t["fno"] for t in out],
                         ["HO1254", "HO1258"])
        self.assertEqual(out[0]["dows"], [str(self.today.weekday())])

    def test_completable_beats_earliest_date(self):
        # CZ8885 has obs today AND +3d: missing = {dow today, dow+3},
        # intersects the window but can NEVER finish in one round
        # (its +3d dow is unreachable today) - while its earliest obs
        # is TODAY, i.e. it still leads under v1.19 ordering. The
        # completable HO1254 (single missing dow tomorrow) must lead
        # instead.
        hist = _hist2(self.today.isoformat(), "CZ8885",
                      self.tomorrow.isoformat(), "HO1254")
        hist["routes"]["r1"]["obs"].append(
            {"date": self.far.isoformat(), "fno": "CZ8885"})
        out = dow_targets(
            hist, {"flights": {}})
        self.assertEqual(out[0]["fno"], "HO1254")

    def test_window_defaults_to_today_tomorrow(self):
        out = dow_targets(_hist2(self.tomorrow.isoformat(), "HO1254"),
                          {"flights": {}})
        self.assertEqual(out, [{"fno": "HO1254", "direction": 2,
                                "dows": [str(self.tomorrow.weekday())]}])

    def test_fill_spends_zero_on_out_of_window(self):
        tmp = _tmp("sh121_zero")
        s = FakeSession()
        stats = sh_fill(s, {"sh_pace": 0}, tmp,
                        _hist2(self.far.isoformat(), "HO1254"))
        self.assertEqual(s.calls, 0)
        self.assertEqual(stats["queries"], 0)

    def test_offsets_focus_on_useful_only(self):
        # obs last week, same weekday as today: the dow target misses
        # exactly TODAY's dow, so the plan must query ONLY offset 0,
        # not (0, 1) - half the budget. (An in-window obs would route
        # through exact_targets first; this exercises the dow path.)
        import core.sh_board as sb
        orig = sb.fetch_flight
        seen_offsets = []

        def spy(session, net_cfg, fno, direction, off, data_dir,
                force=False):
            seen_offsets.append(off)
            return [], "capped"  # stop after first useful query

        sb.fetch_flight = spy
        try:
            sh_fill(FakeSession(), {"sh_pace": 0}, _tmp("sh121_off"),
                    _hist2((self.today - dt.timedelta(days=7)
                            ).isoformat(), "HO1254"))
        finally:
            sb.fetch_flight = orig
        self.assertEqual(seen_offsets, [0])


class TestWiring(unittest.TestCase):
    def test_frontend_renders_filled_stat(self):
        with open("webui/static/app.js", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("时刻行", js)

    def test_stats_carry_filled(self):
        tmp = _tmp("sh121_stats")
        s = FakeSession()
        stats = sh_fill(s, {"sh_pace": 0}, tmp,
                        _hist2(dt.date.today().isoformat(), "HO1254"))
        self.assertIn("filled", stats)
        self.assertNotIn("dow_new", stats)


if __name__ == "__main__":
    unittest.main(verbosity=2)
