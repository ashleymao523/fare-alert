# -*- coding: utf-8 -*-
"""Round-9 probe: touchInnerList flight list API."""
import json
import requests

UA_MB = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Referer": "https://m.flight.qunar.com/h5/flight/oneway?fromCity=%E6%9D%AD%E5%B7%9E&toCity=%E9%87%8D%E5%BA%86&fromDate=2026-09-09",
    "Accept": "application/json",
}
S = requests.Session()
S.trust_env = False

base = "https://m.flight.qunar.com/flight/api/touchInnerList"
variants = [
    {"fromCity": "杭州", "toCity": "重庆", "fromDate": "2026-09-09", "fromCode": "HGH", "toCode": "CKG", "adultNum": "1", "childNum": "0", "babyNum": "0", "cabinType": "0"},
    {"depCity": "杭州", "arrCity": "重庆", "goDate": "2026-09-09", "fromCode": "HGH", "toCode": "CKG"},
]
for i, params in enumerate(variants):
    try:
        r = S.get(base, params=params, headers=UA_MB, timeout=25)
        print(f"[v{i}] {r.status_code} len={len(r.text)}")
        print(r.text[:800])
    except Exception as e:
        print(f"[v{i}] ERR {e}")
    print("-" * 70)

# where is GET_FLIGHT_LIST_URL used in bundle
import re
with open("tools/cache/qbundle0.js", encoding="utf-8", errors="ignore") as f:
    s = f.read()
for m in list(re.finditer(r"GET_FLIGHT_LIST_URL", s))[:5]:
    print("ctx:", s[max(0, m.start() - 300):m.end() + 300].replace("\n", " ")[:600])
    print("-" * 60)
