# -*- coding: utf-8 -*-
"""Check raw seat price field names returned by 12306 for a given pair."""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as runner
from core.config import load_config
from core.trains import get_stations

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = load_config(os.path.join(BASE, "config.json"))
s = runner.make_session(cfg)
stations = get_stations(s, cfg["network"], os.path.join(BASE, "data", "stations.json"))
r = s.get("https://kyfw.12306.cn/otn/leftTicketPrice/query", params={
    "leftTicketDTO.train_date": (dt.date.today() + dt.timedelta(days=1)).isoformat(),
    "leftTicketDTO.from_station": stations["杭州东"]["code"],
    "leftTicketDTO.to_station": stations["重庆北"]["code"],
    "purpose_codes": "ADULT",
}, timeout=25)
for it in r.json().get("data") or []:
    d = it.get("queryLeftNewDTO") or {}
    if d.get("station_train_code") == "D57":
        print(json.dumps({k: v for k, v in d.items() if "price" in k},
                         ensure_ascii=False, indent=1))
