# -*- coding: utf-8 -*-
"""v0.37 verify_release MCP 工具单测: 步骤清洗 / 汇总结构 / health 语义。
全部 mock 子进程与 HTTP, 不发真实请求(红线#1)。"""
import json
import os
import sys
import unittest
import unittest.mock as mock
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_server  # noqa: E402


class FakeCompleted:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def _call(args):
    return mcp_server.tool_verify_release(args)


class TestVerifyRelease(unittest.TestCase):

    def test_bad_steps_rejected(self):
        r = _call({"steps": ["nope"]})
        self.assertTrue(r.get("isError"))

    def test_string_step_accepted(self):
        fake = {"ok": True, "snapshot": {"age_min": 3}, "worker": None}
        resp = MagicMock()
        resp.read.return_value = json.dumps(fake).encode("utf-8")
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        with mock.patch.object(mcp_server.urllib.request, "urlopen", return_value=resp):
            r = _call({"steps": "health"})
        body = json.loads(r["content"][0]["text"])
        self.assertEqual([s["step"] for s in body["steps"]], ["health"])

    def test_subprocess_steps_summary(self):
        fake_out = "line1" + chr(10) + "OK"
        with mock.patch.object(mcp_server.subprocess, "run",
                               return_value=FakeCompleted(0, fake_out)) as pr:
            r = _call({"steps": ["unittest", "ui_check"]})
        self.assertFalse(r.get("isError"))
        body = json.loads(r["content"][0]["text"])
        self.assertTrue(body["all_ok"])
        self.assertEqual([s["step"] for s in body["steps"]], ["unittest", "ui_check"])
        self.assertEqual(pr.call_count, 2)
        self.assertEqual(body["steps"][0]["tail"], ["line1", "OK"])
        self.assertEqual(body["steps"][1]["tail"], ["all checks passed"])

    def test_failure_propagates(self):
        with mock.patch.object(mcp_server.subprocess, "run",
                               return_value=FakeCompleted(1, "FAIL something")):
            r = _call({"steps": ["ui_check"]})
        body = json.loads(r["content"][0]["text"])
        self.assertFalse(body["all_ok"])
        self.assertFalse(body["steps"][0]["ok"])
        self.assertEqual(body["steps"][0]["tail"], ["FAIL something"])

    def test_health_worker_states(self):
        fake = {"ok": True, "snapshot": {"age_min": 5}, "worker": None}
        resp = MagicMock()
        resp.read.return_value = json.dumps(fake).encode("utf-8")
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        with mock.patch.object(mcp_server.urllib.request, "urlopen", return_value=resp):
            r = _call({"steps": ["health"]})
        body = json.loads(r["content"][0]["text"])
        self.assertTrue(body["all_ok"])
        self.assertIn("worker=none", body["steps"][0]["tail"][0])


if __name__ == "__main__":
    unittest.main()
