# -*- coding: utf-8 -*-
"""Find getFlightList action def; kitchen-sink POST attempt."""
import datetime as dt
import re

import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
s = requests.Session()
idx = s.get("https://q.qunarzz.com/flight_touch_react/prd/index@2b1c614e2e46de094693.js",
            headers={"User-Agent": UA_M}, timeout=25).text
for m in list(re.finditer(r"getFlightList", idx))[:3]:
    i = m.start()
    seg = idx[max(0, i - 700):i + 400]
    if "touchInnerList" in seg or "post" in seg or "Post" in seg or "url" in seg:
        print("ACT>>", seg)
        print("=====")
date = (dt.date.today() + dt.timedelta(days=3)).isoformat()
api = "https://m.flight.qunar.com/flight/api/touchInnerList"
hdr = {"User-Agent": UA_M,
       "Referer": "https://m.flight.qunar.com/h5/flight/oneway?fromCity=%E6%9D%AD%E5%B7%9E&toCity=%E9%87%8D%E5%BA%86&fromDate=" + date,
       "Origin": "https://m.flight.qunar.com",
       "Accept": "application/json"}
body = {"depCity": "杭州", "arrCity": "重庆", "goDate": date,
         "from": "touch_oneway", "track": "touch_onsite_flight_list",
         "child": 0, "baby": 0, "cabinType": "0", "sortType": "price",
         "firstRequest": True, "depCode": "HGH", "arrCode": "CKG",
         "sortKey": "price", "lowPrice": "false"}
r = s.post(api, json=body, headers=hdr, timeout=25)
print("KITCHEN", r.status_code, r.text[:300])
