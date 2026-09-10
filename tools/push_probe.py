# -*- coding: utf-8 -*-
"""Probe /api/weekly-push without a configured channel: expect 400 + guide."""
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

req = urllib.request.Request(
    "http://127.0.0.1:8765/api/weekly-push",
    data=json.dumps({}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
try:
    resp = urllib.request.urlopen(req, timeout=30)
    print(resp.status, resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode("utf-8"))
