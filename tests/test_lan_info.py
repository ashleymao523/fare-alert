# -*- coding: utf-8 -*-
"""v0.53: /api/lan-info contract (phone-reachability card data)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


class LanInfoApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = webui.app.test_client()

    def _with_cfg(self, cfg):
        fd, p = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)
        old = webui.CONFIG_PATH
        webui.CONFIG_PATH = p
        self.addCleanup(lambda: (setattr(webui, "CONFIG_PATH", old),
                                 os.remove(p)))

    def test_endpoint_shape(self):
        r = self.client.get("/api/lan-info")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        for key in ("host", "port", "lan_ip", "lan_open", "url"):
            self.assertIn(key, j)
        self.assertIsInstance(j["lan_open"], bool)

    def test_lan_open_builds_url(self):
        self._with_cfg({"webui": {"host": "0.0.0.0", "port": 8765}})
        with mock.patch.object(webui, "_lan_ip", return_value="192.168.1.5"):
            j = self.client.get("/api/lan-info").get_json()
        self.assertTrue(j["lan_open"])
        self.assertEqual(j["lan_ip"], "192.168.1.5")
        self.assertEqual(j["url"], "http://192.168.1.5:8765/")

    def test_local_only_hides_url(self):
        self._with_cfg({"webui": {"host": "127.0.0.1", "port": 8765}})
        with mock.patch.object(webui, "_lan_ip", return_value="192.168.1.5"):
            j = self.client.get("/api/lan-info").get_json()
        self.assertFalse(j["lan_open"])
        self.assertIsNone(j["url"])


if __name__ == "__main__":
    unittest.main()
