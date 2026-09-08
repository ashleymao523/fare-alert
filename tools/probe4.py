# -*- coding: utf-8 -*-
"""Round-4 probe: qunar lowFlight page + its JS bundles."""
import re
import requests

UA_MB = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://m.flight.qunar.com/",
}
S = requests.Session()
S.trust_env = False

# 1. low flight page
for name, url in [
    ("qunar_lowflight", "https://touch.qunar.com/lowFlight/index?cat=touchjpgg&from=touchjpgg"),
    ("qunar_lowflight2", "https://m.flight.qunar.com/h5/flight/static/lowPrice?depCity=%E6%9D%AD%E5%B7%9E&arrCity=%E9%87%8D%E5%BA%86&goDate=2026-09-15"),
]:
    try:
        r = S.get(url, headers=UA_MB, timeout=20)
        with open(f"tools/cache/{name}.html", "w", encoding="utf-8", errors="ignore") as f:
            f.write(r.text)
        print(f"[{name}] {r.status_code} len={len(r.text)}")
    except Exception as e:
        print(f"[{name}] ERR {e}")

# 2. download qunar flight bundles
bundles = [
    "https://q.qunarzz.com/flight_touch_react/prd/index@2b1c614e2e46de094693.js",
    "https://q.qunarzz.com/flight_touch_react/prd/home@7dd41d48f128468e087a.js",
]
for i, u in enumerate(bundles):
    try:
        r = S.get(u, headers=UA_MB, timeout=25)
        p = f"tools/cache/qbundle{i}.js"
        with open(p, "w", encoding="utf-8", errors="ignore") as f:
            f.write(r.text)
        print(f"[bundle{i}] {r.status_code} len={len(r.text)} -> {p}")
    except Exception as e:
        print(f"[bundle{i}] ERR {e}")
