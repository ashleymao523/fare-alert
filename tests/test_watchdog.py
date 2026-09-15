# -*- coding: utf-8 -*-
"""v0.98 watchdog decision core: fail counting, cooldown, no storm."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from tools.watchdog import (COOLDOWN_S, FAILS_BEFORE_RESTART, decide)


class WatchdogDecideTests(unittest.TestCase):
    def test_healthy_resets_fail_counter(self):
        st = {"consecutive_fail": 3}
        action, st2 = decide(st, True, 1000.0)
        self.assertEqual(action, "healthy")
        self.assertEqual(st2["consecutive_fail"], 0)

    def test_first_fail_only_counts(self):
        action, st2 = decide({}, False, 1000.0)
        self.assertEqual(action, "counting")
        self.assertEqual(st2["consecutive_fail"], 1)

    def test_second_fail_restarts_and_sets_cooldown(self):
        action, st2 = decide({"consecutive_fail": 1}, False, 1000.0)
        self.assertEqual(action, "restarting")
        self.assertEqual(st2["last_restart"], 1000.0)
        self.assertEqual(st2["consecutive_fail"], 0)

    def test_cooldown_blocks_back_to_back_restarts(self):
        st = {"consecutive_fail": 1, "last_restart": 1000.0}
        action, st2 = decide(st, False, 1000.0 + COOLDOWN_S - 1)
        self.assertEqual(action, "cooldown")
        self.assertEqual(st2["last_restart"], 1000.0)  # unchanged

    def test_cooldown_expires_allows_restart(self):
        st = {"consecutive_fail": 1, "last_restart": 1000.0}
        action, st2 = decide(st, False, 1000.0 + COOLDOWN_S)
        self.assertEqual(action, "restarting")
        self.assertEqual(st2["last_restart"], 1000.0 + COOLDOWN_S)

    def test_threshold_is_two_fails(self):
        self.assertEqual(FAILS_BEFORE_RESTART, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
