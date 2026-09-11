# -*- coding: utf-8 -*-
"""v0.40 patrol core tests: seams (config/health/push) fully mocked.
Zero real requests (red line #1), zero real pushes. Plus the MCP
delegation contract (transport failures stay tool-errors, not crashes)."""
import json
import os
import sys
import tempfile
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import patrol  # noqa: E402
import mcp_server  # noqa: E402


def _health(age=5, worker=True, covered=7, revive_on=True):
    return {
        "ok": True,
        "snapshot": {"age_min": age},
        "worker": ({"ok": worker, "age_min": 3, "pid": 11} if worker
                   else {"ok": False, "age_min": 999, "pid": 11}),
        "board": {"weekdays_covered": covered},
        "revive": {"supervisor": {"enabled": revive_on}},
    }


class PatrolCoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cfg = {"webui": {"port": 8765},
                     "push": {"bark_key": "", "serverchan_sendkey": "",
                              "weekly_enabled": True}}
        self._push = mock.MagicMock(return_value=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, health, notify=False, cfg=None):
        return patrol.run_patrol(
            self._tmp.name, notify=notify,
            config_loader=lambda p: dict(cfg or self._cfg),
            health_fetch=lambda port: health,
            push=self._push)

    def _archive(self):
        with open(os.path.join(self._tmp.name, "data", "patrol_last.json"),
                  encoding="utf-8") as f:
            return json.load(f)

    def test_healthy_patrol_archives_report(self):
        self._cfg["push"]["bark_key"] = "k"  # healthy needs a ready channel
        doc = self._run(_health())
        self.assertEqual(doc["verdict"], "healthy")
        self.assertEqual(doc["caller"], "manual")
        self.assertEqual(len(doc["checks"]), 5)
        self.assertFalse(doc["notified"])
        arch = self._archive()
        self.assertEqual(arch["verdict"], "healthy")
        self.assertEqual(arch["health"]["worker"], "alive")

    def test_warn_verdict_on_stale_worker_and_thin_board(self):
        doc = self._run(_health(worker=False, covered=2))
        self.assertEqual(doc["verdict"], "warn")
        names = [c["name"] for c in doc["checks"] if c["status"] != "ok"]
        self.assertIn("worker-heartbeat", names)
        self.assertIn("board-dow-coverage", names)

    def test_notify_default_off_never_pushes(self):
        self._run(_health(worker=False))
        self._push.assert_not_called()

    def test_notify_true_pushes_only_when_unhealthy(self):
        self._cfg["push"]["bark_key"] = "k"
        self._run(_health(), notify=True)
        self._push.assert_not_called()
        self._run(_health(worker=False), notify=True)
        self._push.assert_called_once()

    def test_default_fetch_is_loopback_only(self):
        """Contract: the default health seam may only ever talk to
        127.0.0.1, so patrol can never become an external requester."""
        src = open(patrol.__file__, encoding="utf-8").read()
        self.assertIn("127.0.0.1", src)


class PatrolMcpDelegationTests(unittest.TestCase):
    def test_mcp_tool_delegates_to_core(self):
        with mock.patch.object(patrol, "run_patrol") as rp:
            rp.return_value = {"verdict": "healthy", "checks": [], "notified": False}
            r = mcp_server.tool_patrol_run({"notify": True})
        rp.assert_called_once_with(mcp_server.BASE_DIR, notify=True,
                                   caller="mcp")
        self.assertFalse(r.get("isError"))
        self.assertIn("healthy", r["content"][0]["text"])

    def test_transport_failure_is_tool_error_not_crash(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "patrol_run", "arguments": {}}}
        with mock.patch.object(mcp_server.urllib.request, "urlopen",
                               side_effect=OSError("webui down")):
            resp = mcp_server.handle(msg)
        self.assertTrue(resp["result"].get("isError"))


if __name__ == "__main__":
    unittest.main()
