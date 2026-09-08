# -*- coding: utf-8 -*-
"""Probe leftTicketPrice seat-class fields and train types."""
import datetime as dt
import json
import re

import requests

STATION_JS = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
PRICE_QUERY = "https://kyfw.12306.cn/otn/leftTicketPrice/query"
H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://kyfw.12306.cn/otn/leftTicketPrice/init",
}

s = requests.Session()
r = s.get(STATION_JS, headers=H, timeout=20)
m = re.search(r"var station_names ='([^']+)'", r.text)
st = {}
for ent in m.group(1).split("@"):
    if ent:
        p = ent.split("|")
        st[p[1]] = p[2]

date = (dt.date.today() + dt.timedelta(days=1)).isoformat()
r = s.get(PRICE_QUERY, params={
    "leftTicketDTO.train_date": date,
    "leftTicketDTO.from_station": st["杭州东"],
    "leftTicketDTO.to_station": st["重庆北"],
    "purpose_codes": "ADULT",
}, headers=H, timeout=20)
items = r.json().get("data") or []
print("date:", date, "count:", len(items))
for it in items[:8]:
    d = it.get("queryLeftNewDTO") or {}
    prices = {k: v for k, v in d.items() if k.endswith("_price")}
    print(d.get("station_train_code"), d.get("start_time"), "-", d.get("arrive_time"),
          "lishi", d.get("lishi"), json.dumps(prices, ensure_ascii=False))
codes = [(it.get("queryLeftNewDTO") or {}).get("station_train_code") for it in items]
print("all codes:", codes)
