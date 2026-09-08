# -*- coding: utf-8 -*-
"""Fetch lazy flightList chunk; find payload shape; POST touchInnerList."""
import datetime as dt
import json
import re

import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
s = requests.Session()
u = "https://q.qunarzz.com/flight_touch_react/prd/flightList@005f1b22231c34aa831f.js"
b = s.get(u, headers={"User-Agent": UA_M}, timeout=25).text
print("chunk len", len(b))
for pat in ["touchInnerList", "dep", "fromDate"]:
    for m in list(re.finditer(pat, b))[:2]:
        i = m.start()
        print("CTX", pat, ">>", b[max(0, i - 400):i + 200])
        print("=====")
date = (dt.date.today() + dt.timedelta(days=3)).isoformat()
api = "https://m.flight.qunar.com/flight/api/touchInnerList"
hdr = {"User-Agent": UA_M,
       "Referer": "https://m.flight.qunar.com/h5/flight/oneway",
       "Origin": "https://m.flight.qunar.com",
       "Content-Type": "application/json",
       "Accept": "application/json"}
bodies = [
    {"dep": "杭州", "arr": "重庆", "date": date, "from": "touch_oneway"},
    {"depCity": "杭州", "arrCity": "重庆", "fromDate": date, "cabin": "0"},
    {"dep": "杭州", "arr": "重庆", "date": date, "goingDate": date, "from": "touch_oneway", "child": 0, "baby": 0, "cabin": 0},
]
for body in bodies:
    try:
        r = s.post(api, data=json.dumps(body), headers=hdr, timeout=25)
        print("TRY", r.status_code, r.headers.get("content-type", ""), r.text[:260])
        if r.status_code == 200 and r.text[:1] == "{" and "arrTime" in r.text:
            print("WIN", body)
            break
    except Exception as e:
        print("TRY ERR", e)
