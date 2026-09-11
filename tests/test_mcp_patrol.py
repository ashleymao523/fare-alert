# -*- coding: utf-8 -*-
"""v0.39 patrol_run MCP tool tests: fully mocked HTTP, isolated BASE_DIR.
Zero real requests (red line #1), zero real pushes."""
import json
import os
import sys
import tempfile
import unittest
import unittest.mock as mock
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_server  # noqa: E402


def _fake_resp(obj):
    resp = MagicMock()
    resp.read.return_value = json.dumps(obj).encode("utf-8")
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _health(age=5, worker=True, covered=7, revive_on=True):
    return {
        "ok": True,
        "snapshot": {"age_min": age},
        "worker": ({"ok": worker, "age_min": 3, "pid": 11} if worker
                   else {"ok": False, "age_min": 999, "pid": 11}),
        "board": {"weekdays_covered": covered},
        "revive": {"supervisor": {"enabled": revive_on}},
    }


class PatrolTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_base = mcp_server.BASE_DIR
        mcp_server.BASE_DIR = self._tmp.name
        self._orig_load = mcp_server.load_config
        self._cfg = {"webui": {"port": 8765},
                     "push": {"bark_key": "", "serverchan_sendkey": "",
                              "weekly_enabled": True}}
        mcp_server.load_config = lambda p=None: dict(self._cfg)

    def tearDown(self):
        mcp_server.BASE_DIR = self._orig_base
        mcp_server.load_config = self._orig_load
        self._tmp.cleanup()

    def _run(self, health, args=None):
        with mock.patch.object(mcp_server.urllib.request, "urlopen",
                               return_value=_fake_resp(health)):
            return mcp_server.tool_patrol_run(args or {})

    def _archive(self):
        with open(os.path.join(self._tmp.name, "data", "patrol_last.json"),
                  encoding="utf-8") as f:
            return json.load(f)

    def test_healthy_patrol_archives_report(self):
        self._cfg["push"]["bark_key"] = "k"  # healthy needs a ready channel
        r = self._run(_health())
        self.assertFalse(r.get("isError"))
        text = r["content"][0]["text"]
        self.assertIn("healthy", text)
        doc = self._archive()
        self.assertEqual(doc["verdict"], "healthy")
        self.assertEqual(len(doc["checks"]), 5)
        self.assertFalse(doc["notified"])

    def test_warn_verdict_on_stale_worker_and_thin_board(self):
        r = self._run(_health(worker=False, covered=2))
        text = r["content"][0]["text"]
        self.assertIn("warn", text)
        doc = self._archive()
        names = [c["name"] for c in doc["checks"] if c["status"] != "ok"]
        self.assertIn("worker-heartbeat", names)
        self.assertIn("board-dow-coverage", names)

    def test_notify_default_off_never_pushes(self):
        with mock.patch("core.notify.push_all") as pa:
            self._run(_health(worker=False))
        pa.assert_not_called()

    def test_notify_true_pushes_only_when_unhealthy(self):
        self._cfg["push"]["bark_key"] = "k"
        with mock.patch("core.notify.push_all") as pa:
            self._run(_health(), {"notify": True})
            pa.assert_not_called()
            self._run(_health(worker=False), {"notify": True})
        pa.assert_called_once()

    def test_transport_failure_is_tool_error_not_crash(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "patrol_run", "arguments": {}}}
        with mock.patch.object(mcp_server.urllib.request, "urlopen",
                               side_effect=OSError("webui down")):
            resp = mcp_server.handle(msg)
        self.assertTrue(resp["result"].get("isError"))


if __name__ == "__main__":
    unittest.main()
