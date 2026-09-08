# -*- coding: utf-8 -*-
"""Dump raw Qunar price-calendar entries to inspect available fields."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as runner
from core.config import load_config
from core.flights import CALENDAR_URL

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = load_config(os.path.join(BASE, "config.json"))
s = runner.make_session(cfg)
r = s.get(CALENDAR_URL, params={"dep": "杭州", "arr": "重庆", "days": "", "priceType": "1"}, headers={
    "User-Agent": cfg["network"].get("user_agent_mobile", "Mozilla/5.0"),
    "Referer": "https://m.flight.qunar.com/",
    "Accept": "application/json",
}, timeout=25)
j = r.json()
flights = (j.get("data") or {}).get("gflights") or []
print("entries:", len(flights))
for e in flights[:4]:
    print(json.dumps(e, ensure_ascii=False))
