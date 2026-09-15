# -*- coding: utf-8 -*-
"""v0.81: /api/time-coverage per-day matrix contract.

Verifies kind classification (exact/borrow/alt/noref), dow healing
forecast and per-borrow-row promote_on against a synthetic snapshot
plus a board library with a missing weekday.
"""
import json
import os
import sys
import tempfile
import unittest
import datetime as _dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


def _sched_db(missing_dows=()):
    def ent(dep, arr):
        return {"dep": dep, "arr": arr, "from": "杭州", "to": "重庆",
                "airline": "", "craft": "", "src": "airport-board"}
    dows = {str(i): ent("08:00", "10:15") for i in range(7)
            if i not in missing_dows}
    return {"fmt": 2, "updated": 1, "flights": {"CZ100": {"dows": dows}}}


def _snapshot():
    return {"routes": [{
        "id": "r-test", "from_city": "杭州", "to_city": "重庆",
        "intl": False, "window": ["2026-09-15", "2026-09-18"],
        "deals": [
            {"date": "2026-09-15", "flight_no": "CZ100", "dep_time": "08:00",
             "arr_time": "10:15", "dep_src": "airport-board",
             "source": "qunar-calendar"},
            {"date": "2026-09-16", "flight_no": "CZ100", "dep_time": "07:30",
             "arr_time": "09:45", "dep_src": "airport-board-x",
             "source": "qunar-calendar"},
            {"date": "2026-09-17", "flight_no": "", "dep_time": "09:00",
             "arr_time": "11:20", "dep_src": "alt-ref",
             "source": "nearby-ref"},
            {"date": "2026-09-18", "flight_no": "", "dep_time": "",
             "arr_time": "", "dep_src": "", "source": "interp"},
        ],
    }]}



class TimeCoverageApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = webui.app.test_client()

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.missing = (6,)  # library lacks Sunday
        with open(os.path.join(tmp, "flight_sched_db.json"), "w",
                  encoding="utf-8") as f:
            json.dump(_sched_db(self.missing), f, ensure_ascii=False)
        with open(os.path.join(tmp, "snapshot.json"), "w",
                  encoding="utf-8") as f:
            json.dump(_snapshot(), f, ensure_ascii=False)
        old = webui.DATA_DIR
        webui.DATA_DIR = tmp
        self.addCleanup(lambda: setattr(webui, "DATA_DIR", old))

    def test_shape_and_counts(self):
        j = self.client.get("/api/time-coverage").get_json()
        self.assertTrue(j["ok"])
        self.assertIn("dows", j)
        self.assertIn("heal", j)
        self.assertEqual(len(j["routes"]), 1)
        r = j["routes"][0]
        self.assertEqual(r["id"], "r-test")
        self.assertEqual(r["counts"],
                         {"exact": 1, "borrow": 1, "alt": 1, "noref": 1})
        kinds = [d["kind"] for d in r["days"]]
        self.assertEqual(kinds, ["exact", "borrow", "alt", "noref"])

    def test_heal_lists_missing_dow_next_date(self):
        j = self.client.get("/api/time-coverage").get_json()
        self.assertEqual([h["dow"] for h in j["heal"]], [6])
        today = _dt.date.today()
        want = next(today + _dt.timedelta(days=k)
                    for k in range(8)
                    if (today + _dt.timedelta(days=k)).weekday() == 6)
        self.assertEqual(j["heal"][0]["on"], want.isoformat())

    def test_borrow_promote_only_when_own_dow_missing(self):
        j = self.client.get("/api/time-coverage").get_json()
        days = {d["date"]: d for d in j["routes"][0]["days"]}
        # 2026-09-16 is a Wednesday; the synthetic library HAS wed ->
        # no promote promised (board just lacks this flight).
        self.assertNotIn("promote_on", days["2026-09-16"])


if __name__ == "__main__":
    unittest.main()
