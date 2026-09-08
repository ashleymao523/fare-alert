# -*- coding: utf-8 -*-
"""Round-8 probe: inspect full calendar entries + find list API params."""
import json
import re
import requests

UA_MB = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Referer": "https://m.flight.qunar.com/",
}
S = requests.Session()
S.trust_env = False

r = S.get(
    "https://gw.flight.qunar.com/api/f/priceCalendar",
    params={"dep": "杭州", "arr": "重庆", "days": "", "priceType": "1"},
    headers=UA_MB,
    timeout=20,
)
j = r.json()
gf = j["data"]["gflights"]
print("total days:", len(gf))
print("sample entries 2026-09-08..12:")
for e in gf[:5]:
    print(" ", json.dumps(e, ensure_ascii=False))
# lowest 10 in next 60 days
import datetime
today = datetime.date(2026, 9, 8)
win = [e for e in gf if e.get("price") and e["date"] >= "2026-09-09" and e["date"] <= "2026-11-07"]
win.sort(key=lambda x: int(x["price"]))
print("lowest 10 in 60d window:")
for e in win[:10]:
    print(" ", e["date"], e["price"], e["code"])

# find list api params in bundles
for path in ["tools/cache/qbundle0.js", "tools/cache/qbundle1.js"]:
    with open(path, encoding="utf-8", errors="ignore") as f:
        s = f.read()
    for kw in ["fromCity", "fromDate", "sortType"]:
        for m in list(re.finditer(kw, s))[:3]:
            print(f"ctx[{path}:{kw}]:", s[max(0, m.start() - 200):m.end() + 200].replace("\n", " ")[:400])
        print("-" * 60)
