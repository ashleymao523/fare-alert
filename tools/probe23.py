# -*- coding: utf-8 -*-
"""POST touchInnerList with depCity/arrCity/goDate body variants."""
import datetime as dt
import json

import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
s = requests.Session()
date = (dt.date.today() + dt.timedelta(days=3)).isoformat()
api = "https://m.flight.qunar.com/flight/api/touchInnerList"
hdr = {"User-Agent": UA_M,
       "Referer": "https://m.flight.qunar.com/h5/flight/oneway",
       "Origin": "https://m.flight.qunar.com",
       "Accept": "application/json"}
bodies = [
    {"depCity": "杭州", "arrCity": "重庆", "goDate": date},
    {"depCity": "杭州", "arrCity": "重庆", "goDate": date, "from": "touch_oneway"},
    {"depCity": "杭州", "arrCity": "重庆", "goDate": date, "from": "touch_oneway",
     "child": 0, "baby": 0, "cabin": "0"},
    {"depCity": "杭州", "arrCity": "重庆", "goDate": date, "from": "touch_oneway",
     "child": 0, "baby": 0, "cabinType": "0", "sortKey": "price"},
    {"startCity": "杭州", "destCity": "重庆", "startDate": date},
]
for body in bodies:
    try:
        r = s.post(api, json=body, headers=hdr, timeout=25)
        ok = r.status_code == 200 and r.text[:1] == "{"
        print("TRY", list(body.keys()), "->", r.status_code, r.text[:200])
        if ok and '"ret":true' in r.text:
            j = r.json()
            open("cache/touchlist.json", "w", encoding="utf-8").write(r.text)
            print("SAVED full response, keys:", list((j.get("data") or {}).keys())[:20])
            break
    except Exception as e:
        print("TRY ERR", e)
