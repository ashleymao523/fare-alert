# -*- coding: utf-8 -*-
"""v0.41 core.reenrich tests: offline snapshot time replay.
Zero network (session=None replay path), tmp-dir isolated."""
import json
import glob
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import reenrich  # noqa: E402


def _write(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def _read(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class ReenrichCoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = self._tmp.name
        # a Sunday board entry for GJ8888 (the deal below is a Sunday)
        _write(os.path.join(root, "data", "flight_sched_db.json"), {
            "updated": 1, "flights": {"GJ8888": {"dows": {
                "6": {"dep": "07:30", "arr": "10:05", "from": "杭州",
                      "to": "重庆", "src": "airport-board"}}}}})
        _write(os.path.join(root, "config.json"), {})
        _write(os.path.join(root, "data", "snapshot.json"), {"routes": [{
            "id": "t1", "from_city": "杭州", "to_city": "重庆",
            "window": ["2026-09-13", "2026-09-13"],
            "deals": [{
                "date": "2026-09-13", "bare_price": 300.0,
                "flight_no": "GJ8888", "source": "qunar-calendar",
                "url": "https://example.com", "dep_time": "", "arr_time": "",
                "time_src": "", "dep_src": "", "arr_src": "",
            }],
            "time_coverage": {"total": 1, "dep_exact": 0, "dep_borrow": 0,
                              "dep_missing": 1, "arr_exact": 0,
                              "arr_borrow": 0, "arr_est": 0,
                              "arr_missing": 1},
        }]})
        self.root = root

    def tearDown(self):
        self._tmp.cleanup()

    def test_replay_fills_times_and_coverage(self):
        out = reenrich.reenrich_snapshot(self.root)
        self.assertEqual(out["routes"], 1)
        self.assertEqual(out["dep_covered"], 1)
        self.assertEqual(out["dep_total"], 1)
        snap = _read(os.path.join(self.root, "data", "snapshot.json"))
        deal = snap["routes"][0]["deals"][0]
        self.assertEqual(deal["dep_time"], "07:30")
        self.assertEqual(deal["arr_time"], "10:05")
        self.assertEqual(deal["dep_src"], "airport-board")
        self.assertEqual(snap["routes"][0]["time_coverage"]["dep_exact"], 1)

    def test_dry_run_leaves_snapshot_untouched(self):
        reenrich.reenrich_snapshot(self.root, dry=True)
        snap = _read(os.path.join(self.root, "data", "snapshot.json"))
        deal = snap["routes"][0]["deals"][0]
        self.assertEqual(deal["dep_time"], "")
        self.assertEqual(snap["routes"][0]["time_coverage"]["dep_missing"], 1)

    def test_amadeus_times_survive_replay(self):
        snap_path = os.path.join(self.root, "data", "snapshot.json")
        snap = _read(snap_path)
        snap["routes"][0]["deals"][0]["time_src"] = "amadeus"
        snap["routes"][0]["deals"][0]["dep_time"] = "08:00"
        snap["routes"][0]["deals"][0]["arr_time"] = "10:30"
        _write(snap_path, snap)
        reenrich.reenrich_snapshot(self.root)
        snap = _read(snap_path)
        deal = snap["routes"][0]["deals"][0]
        self.assertEqual(deal["dep_time"], "08:00")  # strongest source wins
        self.assertEqual(deal["time_src"], "amadeus")

    def test_missing_snapshot_is_not_an_error(self):
        os.remove(os.path.join(self.root, "data", "snapshot.json"))
        out = reenrich.reenrich_snapshot(self.root)
        self.assertEqual(out["routes"], 0)
        self.assertFalse(out["changed"])

    def test_unchanged_rerun_skips_write(self):
        """v0.41 review P2: a rerun that moves nothing must not touch
        the snapshot or pile up another .bak-* (daily patrol path)."""
        snap_path = os.path.join(self.root, "data", "snapshot.json")
        out1 = reenrich.reenrich_snapshot(self.root)
        baks1 = glob.glob(snap_path + ".bak-*")
        out2 = reenrich.reenrich_snapshot(self.root)
        baks2 = glob.glob(snap_path + ".bak-*")
        self.assertTrue(out1["changed"])
        self.assertFalse(out2["changed"])
        self.assertNotIn("write_error", out2)
        self.assertEqual(len(baks1), len(baks2))


if __name__ == "__main__":
    unittest.main()
