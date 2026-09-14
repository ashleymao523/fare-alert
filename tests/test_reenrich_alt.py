# -*- coding: utf-8 -*-
"""v0.42 regression: codeshare deals gain alt_times on re-enrich and
the change persists (changed=True) even when coverage counts are flat."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class ReenrichAltTimesTests(unittest.TestCase):
    def _make_repo(self, tmp):
        os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
        snap = {
            "routes": [{
                "id": "t", "from_city": "杭州", "to_city": "重庆",
                "window": ["2026-10-25", "2026-10-25"],
                "time_coverage": {"total": 1, "dep_exact": 0,
                                  "dep_borrow": 0, "dep_missing": 1,
                                  "arr_exact": 0, "arr_borrow": 0,
                                  "arr_est": 0, "arr_missing": 1},
                "deals": [{
                    "date": "2026-10-25", "bare_price": 300,
                    "flight_no": "SC2114/SC2135", "source": "qunar-calendar",
                    "dep_time": "", "alt_times": [],
                }],
            }]
        }
        with open(os.path.join(tmp, "data", "snapshot.json"), "w",
                  encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False)
        # board db with one known HGH->CKG departure on sunday (25th)
        db = {"updated": "", "flights": {"CZ7117": {"dows": {
            "0": {"dep": "06:20", "arr": "09:00", "from": "杭州",
                  "to": "重庆", "src": "airport-board"}}}}}
        with open(os.path.join(tmp, "data", "flight_sched_db.json"), "w",
                  encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False)
        return snap

    def test_alt_times_change_persists(self):
        from core.reenrich import reenrich_snapshot
        with tempfile.TemporaryDirectory() as tmp:
            self._make_repo(tmp)
            out = reenrich_snapshot(tmp)
            self.assertTrue(out["changed"],
                            "alt_times move must mark changed")
            with open(os.path.join(tmp, "data", "snapshot.json"),
                      encoding="utf-8") as f:
                snap = json.load(f)
            d = snap["routes"][0]["deals"][0]
            self.assertFalse(d["dep_time"])       # codeshare stays unknown
            self.assertTrue(d["alt_times"])        # reference rows attached
            # idempotent second run reports no change
            out2 = reenrich_snapshot(tmp)
            self.assertFalse(out2["changed"])


if __name__ == "__main__":
    unittest.main()
