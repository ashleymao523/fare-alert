# -*- coding: utf-8 -*-
"""Extract touchInnerList param shape from bundle, then live-test the api."""
import datetime as dt
import re

import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
s = requests.Session()
b = s.get("https://q.qunarzz.com/flight_touch_react/prd/index@2b1c614e2e46de094693.js",
          headers={"User-Agent": UA_M}, timeout=25).text
for m in list(re.finditer(r"touchInnerList", b))[:3]:
    i = m.start()
    print("CTX>>", b[max(0, i - 500):i + 300])
    print("=====")
date = (dt.date.today() + dt.timedelta(days=3)).isoformat()
base = "https://m.flight.qunar.com/flight/api/touchInnerList"
tests = [
    {"dep": "杭州", "arr": "重庆", "date": date, "from": "touch_oneway"},
    {"depCity": "杭州", "arrCity": "重庆", "fromDate": date},
    {"dep": "HGH", "arr": "CKG", "date": date, "from": "touch_oneway"},
]
for t in tests:
    try:
        r = s.get(base, params=t,
                  headers={"User-Agent": UA_M,
                           "Referer": "https://m.flight.qunar.com/h5/flight/oneway",
                           "Accept": "application/json"},
                  timeout=20)
        print("TRY", list(t.values()), r.status_code,
              r.headers.get("content-type", ""), r.text[:220])
    except Exception as e:
        print("TRY ERR", e)
