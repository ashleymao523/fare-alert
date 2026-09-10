# -*- coding: utf-8 -*-
"""v0.18 review fix: channel failures must surface as :ERR markers.
Otherwise an invalid Bark/ServerChan key silently consumes the 7d timer."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import notify


class _Resp:
    def __init__(self, code, body=None):
        self.status_code = code
        self._body = body

    def json(self):
        return self._body


class _Log:
    def info(self, *a, **k):
        pass


class TestPushMarkers(unittest.TestCase):
    def test_bark_non_200_is_err(self):
        with mock.patch.object(notify.requests, "post",
                               return_value=_Resp(400)):
            res = notify.push_all({"push": {"bark_key": "bad"}}, _Log(),
                                  "t", "b")
        self.assertTrue(any(x.startswith("bark:ERR HTTP 400") for x in res))

    def test_bark_200_ok(self):
        with mock.patch.object(notify.requests, "post",
                               return_value=_Resp(200)):
            res = notify.push_all({"push": {"bark_key": "k"}}, _Log(), "t", "b")
        self.assertIn("bark:200", res)

    def test_serverchan_error_body_is_err(self):
        with mock.patch.object(notify.requests, "post",
                               return_value=_Resp(200, {"code": 40001})):
            res = notify.push_all({"push": {"serverchan_sendkey": "SCTx"}},
                                  _Log(), "t", "b")
        self.assertTrue(any("serverchan:ERR" in x for x in res))

    def test_serverchan_ok(self):
        with mock.patch.object(notify.requests, "post",
                               return_value=_Resp(200, {"code": 0})):
            res = notify.push_all({"push": {"serverchan_sendkey": "SCTx"}},
                                  _Log(), "t", "b")
        self.assertIn("serverchan:200", res)


if __name__ == "__main__":
    unittest.main(verbosity=1)
