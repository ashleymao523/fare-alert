# -*- coding: utf-8 -*-
"""Try candidate Qunar H5 endpoints that may return flight dep/arr times."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as runner
from core.config import load_config

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = load_config(os.path.join(BASE, "config.json"))
s = runner.make_session(cfg)
H = {
    "User-Agent": cfg["network"].get("user_agent_mobile", "Mozilla/5.0"),
    "Referer": "https://m.flight.qunar.com/h5/flight/oneway",
    "Accept": "application/json",
}

CANDIDATES = [
    ("oneway-list-1", "https://m.flight.qunar.com/h5/flight/api/domestic/searchOnewayFlight", {
        "depCity": "杭州", "arrCity": "重庆", "goDate": "2026-09-09",
        "from": "QunarH5", "child": "0", "baby": "0", "cabinType": "0"}),
    ("oneway-list-2", "https://m.flight.qunar.com/h5/flight/api/domestic/OnewayList", {
        "depCity": "杭州", "arrCity": "重庆", "goDate": "2026-09-09",
        "child": "0", "baby": "0", "cabinType": "0"}),
    ("oneway-list-3", "https://touch.flight.qunar.com/api/flight/flightList", {
        "depCity": "杭州", "arrCity": "重庆", "goDate": "2026-09-09"}),
    ("oneway-list-4", "https://m.flight.qunar.com/h5/flight/api/domestic/flightList", {
        "dep": "杭州", "arr": "重庆", "date": "2026-09-09"}),
]

for name, url, params in CANDIDATES:
    try:
        r = s.get(url, params=params, headers=H, timeout=15)
        ct = r.headers.get("content-type", "")
        head = r.text[:220].replace("\n", " ")
        print(name, r.status_code, ct.split(";")[0], head)
    except Exception as e:
        print(name, "ERR", str(e)[:120])
