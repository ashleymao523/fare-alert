# -*- coding: utf-8 -*-
"""Probe flight schedule sources (dep/arr times) for calendar flight numbers."""
import datetime as dt
import json
import re

import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
UA_D = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

s = requests.Session()
date = (dt.date.today() + dt.timedelta(days=3)).isoformat()

fno = "GJ8131"
try:
    with open("../data/snapshot.json", encoding="utf-8") as f:
        snap = json.load(f)
    deals = snap["routes"][0]["deals"]
    if deals:
        fno = deals[0]["flight_no"]
except Exception:
    pass
print("probe flight_no =", fno, "date =", date)

try:
    r = s.get("https://www.umetrip.com/mskyweb/fs/fc.do",
              params={"dep": "杭州", "arr": "重庆", "date": date, "channel": ""},
              headers={"User-Agent": UA_M, "Referer": "https://www.umetrip.com/",
                       "Accept": "application/json"},
              timeout=15)
    ct = r.headers.get("content-type", "")
    head = r.text[:400]
    print("A umetrip", r.status_code, ct, head)
except Exception as e:
    print("A umetrip ERR", e)

try:
    r = s.get("https://www.variflight.com/flight/fnum/" + fno + ".html",
              params={"AE71649A58c77": "", "fdate": date},
              headers={"User-Agent": UA_D, "Referer": "https://www.variflight.com/"},
              timeout=15)
    times = re.findall(r"[0-9]{2}:[0-9]{2}", r.text)
    print("B variflight", r.status_code, r.headers.get("content-type", ""),
          "len", len(r.text), "times sample:", times[:10])
except Exception as e:
    print("B variflight ERR", e)
