# -*- coding: utf-8 -*-
"""Dig SSR state in H5 page + flightlist api param shape from bundle."""
import datetime as dt
import os
import re

import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
s = requests.Session()
date = (dt.date.today() + dt.timedelta(days=3)).isoformat()
url = ("https://m.flight.qunar.com/h5/flight/oneway?fromCity=%E6%9D%AD%E5%B7%9E"
        "&toCity=%E9%87%8D%E5%BA%86&fromDate=" + date + "&cabintype=0&adultnum=1")
os.makedirs("cache", exist_ok=True)
page_file = os.path.join("cache", "h5_oneway.html")
if os.path.exists(page_file):
    html = open(page_file, encoding="utf-8").read()
else:
    html = s.get(url, headers={"User-Agent": UA_M}, timeout=25).text
    open(page_file, "w", encoding="utf-8").write(html)
print("page len", len(html))
fnos = re.findall(r"[A-Z][A-Z0-9][0-9]{4}", html)
print("flight-no-like tokens:", len(fnos), sorted(set(fnos))[:15])
for pat in ["flightNo", "depAirport", "arrAirport", "lowestPrice", "flightList",
            "priceList", "recommendFlight", "infraredData"]:
    cnt = len(re.findall(re.escape(pat), html))
    i = html.find(pat)
    print("PAT", pat, "count", cnt, "at", i)
    if i >= 0:
        print("  >>", html[i:i + 300].replace(chr(10), " "))
burl = "https://q.qunarzz.com/flight_touch_react/prd/bundle@abec3fe55b31deb59c49.js"
b = s.get(burl, headers={"User-Agent": UA_M}, timeout=25).text
for m in list(re.finditer(r"flightlist", b))[:4]:
    i = m.start()
    print("CTX", b[max(0, i - 350):i + 250])
    print("-----")
