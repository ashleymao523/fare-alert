# -*- coding: utf-8 -*-
"""v0.56: alert.drop_pct / drop_abs validation via _validate_config."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


class DropConfigTests(unittest.TestCase):
    def _validate(self, body):
        return webui._validate_config(body, copy.deepcopy(body))

    def test_defaults_fill(self):
        cfg = webui.load_config(webui.CONFIG_PATH)
        cfg["alert"] = {}
        out = self._validate(cfg)["alert"]
        self.assertEqual(out["drop_pct"], 15.0)
        self.assertEqual(out["drop_abs"], 50.0)

    def test_valid_values_pass(self):
        cfg = webui.load_config(webui.CONFIG_PATH)
        cfg["alert"] = {"drop_pct": 20, "drop_abs": 80}
        out = self._validate(cfg)["alert"]
        self.assertEqual(out["drop_pct"], 20.0)
        self.assertEqual(out["drop_abs"], 80.0)

    def test_clamp_out_of_range(self):
        cfg = webui.load_config(webui.CONFIG_PATH)
        cfg["alert"] = {"drop_pct": 0.5, "drop_abs": -5}
        out = self._validate(cfg)["alert"]
        self.assertEqual(out["drop_pct"], 1.0)
        self.assertEqual(out["drop_abs"], 0.0)
        cfg["alert"] = {"drop_pct": 200, "drop_abs": 99999}
        out = self._validate(cfg)["alert"]
        self.assertEqual(out["drop_pct"], 90.0)
        self.assertEqual(out["drop_abs"], 5000.0)

    def test_string_coercion(self):
        # number inputs may submit strings; float() + clamp must cope
        cfg = webui.load_config(webui.CONFIG_PATH)
        cfg["alert"] = {"drop_pct": "25", "drop_abs": "60"}
        out = self._validate(cfg)["alert"]
        self.assertEqual(out["drop_pct"], 25.0)
        self.assertEqual(out["drop_abs"], 60.0)


if __name__ == "__main__":
    unittest.main()
