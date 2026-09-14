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

    def test_cabin_v1_alias(self):
        r0 = self.client.get("/api/cabin")
        r1 = self.client.get("/api/v1/cabin")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r0.get_json(), r1.get_json())


if __name__ == "__main__":
    unittest.main()
