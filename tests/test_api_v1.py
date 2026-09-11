# -*- coding: utf-8 -*-
"""v0.25 API v1 alias contract: every /api/* route is mirrored /api/v1/*.

Old paths stay first-class; /api/v1 is the pinned contract for a future
standalone frontend. Read-only endpoints only (no config/snapshot writes).
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


class ApiV1AliasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = webui.app.test_client()

    def test_every_api_route_has_v1_alias(self):
        v0 = {r.rule: r.endpoint for r in webui.app.url_map.iter_rules()
              if r.rule.startswith("/api/") and not r.rule.startswith("/api/v1/")}
        v1 = {r.rule: r.endpoint for r in webui.app.url_map.iter_rules()
              if r.rule.startswith("/api/v1/")}
        self.assertTrue(v0, "no api routes found")
        for rule, endpoint in v0.items():
            mirrored = "/api/v1" + rule[len("/api"):]
            self.assertIn(mirrored, v1, "missing v1 alias for " + rule)
            self.assertEqual(v1[mirrored], endpoint)

    def test_v1_snapshot_matches_v0(self):
        r0 = self.client.get("/api/snapshot")
        r1 = self.client.get("/api/v1/snapshot")
        self.assertEqual(r0.status_code, 200)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r0.get_json(), r1.get_json())

    def test_v1_post_methods_preserved(self):
        """POST-only routes keep their methods under /api/v1 (400 on bad
        input proves routing + method match, without any write)."""
        r = self.client.post("/api/v1/reverse-search",
                             data=json.dumps({"bad": 1}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_v1_weekly_report_has_channel_ready(self):
        r = self.client.get("/api/v1/weekly-report")
        self.assertEqual(r.status_code, 200)
        self.assertIn("channel_ready", r.get_json())

    def test_v1_weekly_report_push_observability(self):
        """v0.39: per-channel readiness + weekly timer state surfaced."""
        r = self.client.get("/api/v1/weekly-report")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        for k in ("channels", "retry_waiting", "last_push_at", "next_push_at"):
            self.assertIn(k, d)
        self.assertIn("bark", d["channels"])
        self.assertIn("serverchan", d["channels"])


if __name__ == "__main__":
    unittest.main()
