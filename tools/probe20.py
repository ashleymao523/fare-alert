# -*- coding: utf-8 -*-
"""Grep qunar bundles for XHR data-api path candidates, then test the best one."""
import re
import requests

UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
s = requests.Session()
bundles = [
    "https://q.qunarzz.com/flight_touch_react/prd/bundle@abec3fe55b31deb59c49.js",
    "https://q.qunarzz.com/flight_touch_react/prd/index@2b1c614e2e46de094693.js",
    "https://q.qunarzz.com/flight_www_react/prd/static/godEyeNoMark.min.js",
]
cands = set()
for u in bundles:
    try:
        b = s.get(u, headers={"User-Agent": UA_M}, timeout=25).text
    except Exception as e:
        print("ERR", u[-30:], e)
        continue
    paths = re.findall(r"['\"]((?:https?://[a-z0-9.]*qunar[^'\"]*|/[a-zA-Z0-9/_-]{3,60}))['\"]", b)
    for p in paths:
        if re.search(r"flight|list|query|search|ncs|inter", p) and not p.endswith((".js", ".css", ".png", ".html")):
            cands.add(p)
    print(u.split("/")[-1][:34], "len", len(b), "cands so far", len(cands))
print("CANDIDATES:")
for c in sorted(cands)[:40]:
    print(" ", c)
