# -*- coding: utf-8 -*-
"""v0.42: /api/cabin contract (config echo + ring history + v1 alias)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


class CabinApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = webui.app.test_client()

    def test_cabin_endpoint_shape(self):
        r = self.client.get("/api/cabin")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertIn("config", j)
        self.assertIn("history", j)
        self.assertIn("routes", j["history"])
        # defaults echo even when disabled
        self.assertIn("default_to_city", j["config"])
        self.assertEqual(j["config"]["default_to_city"], "杭州")
        # v0.52: record-low alerting toggle echoes (default on)
        self.assertTrue(j["config"]["alert_record_low"])
        # v0.47: destination list + refresh cadence + collected routes
        self.assertEqual(j["config"]["to_cities"], ["杭州"])
        self.assertIn("interval_minutes", j["refresh"])
        self.assertIn("last_cycle_ts", j["refresh"])
        self.assertIn("next_cycle_ts", j["refresh"])
        self.assertIsInstance(j["qualifying_routes"], list)

    def test_cabin_v1_alias(self):
        r0 = self.client.get("/api/cabin")
        r1 = self.client.get("/api/v1/cabin")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r0.get_json(), r1.get_json())

    def test_cabin_mirror_qualifying_routes(self):
        # v0.50: a HGH->CKG route auto-derives the mirrored CKG->HGH
        # watch leg - qualifying_routes reports the real leg + mirror flag
        import json as _json
        import tempfile
        cfg = {"cabin_watch": {"enabled": True, "to_cities": ["杭州"]},
               "routes": [{"from_city": "杭州", "to_city": "重庆"},
                          {"from_city": "成都", "to_city": "杭州"}]}
        fd, p = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(p, "w", encoding="utf-8") as f:
            _json.dump(cfg, f, ensure_ascii=False)
        old = webui.CONFIG_PATH
        webui.CONFIG_PATH = p
        try:
            j = self.client.get("/api/cabin").get_json()
            self.assertIn({"from_city": "重庆", "to_city": "杭州",
                           "mirror": True}, j["qualifying_routes"])
            self.assertIn({"from_city": "成都", "to_city": "杭州",
                           "mirror": False}, j["qualifying_routes"])
        finally:
            webui.CONFIG_PATH = old
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
