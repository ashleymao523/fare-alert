# -*- coding: utf-8 -*-
"""v0.54: /api/board explorer contract (city pair / flight-no search)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


def _db():
    def ent(dep, arr, frm, to, al="南航", craft="A320"):
        return {"dep": dep, "arr": arr, "from": frm, "to": to,
                "airline": al, "craft": craft, "src": "airport-board"}
    return {"updated": 1, "flights": {
        "CZ100": {"dows": {"0": ent("08:00", "10:15", "杭州", "重庆"),
                           "3": ent("08:00", "10:15", "杭州", "重庆")}},
        "MU200": {"dows": {"0": ent("07:30", "09:45", "重庆", "杭州"),
                           "1": ent("07:30", "09:45", "重庆", "杭州")}},
        "3U300": {"dows": {"4": ent("12:00", "14:10", "郑州", "杭州")}},
    }}


class BoardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = webui.app.test_client()

    def setUp(self):
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, "flight_sched_db.json"), "w",
                  encoding="utf-8") as f:
            json.dump(_db(), f, ensure_ascii=False)
        old = webui.DATA_DIR
        webui.DATA_DIR = tmp
        self.addCleanup(lambda: setattr(webui, "DATA_DIR", old))

    def test_shape(self):
        r = self.client.get("/api/board")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertTrue(j["ok"])
        self.assertIn("flights", j)
        self.assertIn("library", j)
        self.assertIn("total", j)
        row = j["flights"][0]
        for key in ("no", "from", "to", "dep", "arr", "airline",
                    "craft", "dows", "src"):
            self.assertIn(key, row)

    def test_sorted_by_dep_and_from_filter(self):
        j = self.client.get("/api/board?from=" + "杭州").get_json()
        nos = [f["no"] for f in j["flights"]]
        self.assertIn("CZ100", nos)
        self.assertNotIn("MU200", nos)
        # MU200 departs 07:30, earlier than CZ100 08:00 -> sorted first
        all_nos = [f["no"] for f in
                   self.client.get("/api/board").get_json()["flights"]]
        self.assertEqual(all_nos[0], "MU200")

    def test_to_filter_and_flight_no_query(self):
        j = self.client.get("/api/board?to=重庆").get_json()
        self.assertEqual([f["no"] for f in j["flights"]], ["CZ100"])
        # lowercase input must still match (upper-cased server-side)
        j = self.client.get("/api/board?q=mu2").get_json()
        self.assertEqual([f["no"] for f in j["flights"]], ["MU200"])

    def test_dows_sorted_ints(self):
        j = self.client.get("/api/board?q=CZ100").get_json()
        self.assertEqual(j["flights"][0]["dows"], [0, 3])

    def test_limit(self):
        j = self.client.get("/api/board?limit=1").get_json()
        self.assertEqual(len(j["flights"]), 1)
        self.assertEqual(j["total"], 1)


if __name__ == "__main__":
    unittest.main()
