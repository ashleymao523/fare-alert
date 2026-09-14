# -*- coding: utf-8 -*-
"""v0.43: cabin_watch config validation via _validate_config."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


def _base_body():
    cfg = webui.load_config(webui.CONFIG_PATH)
    return cfg


class CabinWatchConfigTests(unittest.TestCase):
    def _validate(self, body):
        return webui._validate_config(body, copy.deepcopy(body))

    def test_valid_cabin_watch_passes(self):
        cfg = _base_body()
        cfg["cabin_watch"] = {
            "enabled": True, "cabins": ["business"],
            "default_to_city": "杭州", "threshold_total": 1200,
            "cooldown_hours": 6, "watch_from_cities": ["重庆", "成都"],
        }
        out = self._validate(cfg)
        cw = out["cabin_watch"]
        self.assertTrue(cw["enabled"])
        self.assertEqual(cw["threshold_total"], 1200.0)
        self.assertEqual(cw["cooldown_hours"], 6.0)
        self.assertEqual(cw["watch_from_cities"], ["成都", "重庆"])

    def test_defaults_fill_and_clean(self):
        cfg = _base_body()
        cfg["cabin_watch"] = {
            "enabled": True,
            "watch_from_cities": [" 重庆 ", "", "重庆", "北京"],
        }
        out = self._validate(cfg)
        cw = out["cabin_watch"]
        self.assertEqual(cw["default_to_city"], "杭州")
        self.assertEqual(cw["cabins"], ["business"])
        self.assertEqual(cw["threshold_total"], 1500.0)
        self.assertEqual(cw["watch_from_cities"], ["北京", "重庆"])

    def test_bad_threshold_rejected(self):
        cfg = _base_body()
        cfg["cabin_watch"] = {"threshold_total": -1}
        with self.assertRaises(ValueError):
            self._validate(cfg)

    def test_bad_cabins_falls_back(self):
        cfg = _base_body()
        cfg["cabin_watch"] = {"cabins": ["steerage"]}
        out = self._validate(cfg)
        self.assertEqual(out["cabin_watch"]["cabins"], ["business"])

    def test_to_cities_list_validated(self):
        # v0.47: destinations are a list; order kept, dupes stripped
        cfg = _base_body()
        cfg["cabin_watch"] = {"enabled": True,
                              "to_cities": [" 杭州 ", "", "宁波", "杭州"]}
        out = self._validate(cfg)
        cw = out["cabin_watch"]
        self.assertEqual(cw["to_cities"], ["杭州", "宁波"])
        self.assertEqual(cw["default_to_city"], "杭州")

    def test_to_cities_falls_back_to_legacy_field(self):
        cfg = _base_body()
        cfg["cabin_watch"] = {"enabled": True, "default_to_city": "宁波"}
        out = self._validate(cfg)
        self.assertEqual(out["cabin_watch"]["to_cities"], ["宁波"])

    def test_bad_to_cities_rejected(self):
        cfg = _base_body()
        cfg["cabin_watch"] = {"to_cities": "杭州"}
        with self.assertRaises(ValueError):
            self._validate(cfg)

    def test_non_list_from_cities_rejected(self):
        cfg = _base_body()
        cfg["cabin_watch"] = {"watch_from_cities": "重庆"}
        with self.assertRaises(ValueError):
            self._validate(cfg)


if __name__ == "__main__":
    unittest.main()
