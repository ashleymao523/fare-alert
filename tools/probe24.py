# -*- coding: utf-8 -*-
"""Last probe: goFlight field content + wide context of list ajax payload."""
import re

import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
s = requests.Session()
r = s.get("https://gw.flight.qunar.com/api/f/priceCalendar",
          params={"dep": "杭州", "arr": "重庆", "days": "", "priceType": "1"},
          headers={"User-Agent": UA_M, "Referer": "https://m.flight.qunar.com/",
                   "Accept": "application/json"}, timeout=20)
j = r.json()
g = ((j.get("data") or {}).get("gflights") or [])
print("calendar entries:", len(g))
if g:
    print("entry[0]:", g[0])
b = s.get("https://q.qunarzz.com/flight_touch_react/prd/flightList@005f1b22231c34aa831f.js",
          headers={"User-Agent": UA_M}, timeout=25).text
for m in list(re.finditer(r"depCity", b))[:4]:
    i = m.start()
    print("WCTX >>", b[max(0, i - 900):i + 300])
    print("=====")
i = b.find("nextDays")
print("nextDays at", i)
if i >= 0:
    print("  >>", b[max(0, i - 300):i + 200])
