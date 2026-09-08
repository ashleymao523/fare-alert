# -*- coding: utf-8 -*-
"""Inspect Qunar H5 oneway page: SSR state or real XHR api paths."""
import datetime as dt
import re

import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
s = requests.Session()
date = (dt.date.today() + dt.timedelta(days=3)).isoformat()
url = ("https://m.flight.qunar.com/h5/flight/oneway?fromCity=%E6%9D%AD%E5%B7%9E"
        "&toCity=%E9%87%8D%E5%BA%86&fromDate=" + date + "&cabintype=0&adultnum=1")
r = s.get(url, headers={"User-Agent": UA_M, "Accept": "text/html"}, timeout=20)
print("page", r.status_code, "len", len(r.text))
for pat in ["INITIAL_STATE", "__NUXT__", "depTime", "arrTime", "flightInfo",
            "window.__", "priceCalendar"]:
    i = r.text.find(pat)
    print("PAT", pat, "at", i)
    if i >= 0:
        seg = r.text[i:i + 260]
        print("  >>", seg)
srcs = re.findall(r"src=\"([^\"]+\.js)\"", r.text)
print("scripts:", srcs[:12])
for j in [x for x in srcs if "flight" in x or "chunk" in x][:2]:
    u = j if j.startswith("http") else "https://m.flight.qunar.com" + j
    try:
        b = s.get(u, headers={"User-Agent": UA_M, "Referer": url}, timeout=20)
        apis = sorted(set(re.findall(r"\"(/[a-zA-Z0-9/_-]{4,60})\"", b.text)))
        hits = [a for a in apis if "api" in a or "flight" in a or "search" in a]
        print("bundle", u[-40:], "len", len(b.text), "api hits:", hits[:20])
    except Exception as e:
        print("bundle ERR", u[-40:], e)
