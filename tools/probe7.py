# -*- coding: utf-8 -*-
"""Round-7 probe: call qunar priceCalendar API."""
import json
import requests

UA_MB = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Referer": "https://m.flight.qunar.com/",
}
S = requests.Session()
S.trust_env = False

variants = [
    ("codes", {"dep": "HGH", "arr": "CKG", "days": "", "priceType": "1"}),
    ("names", {"dep": "杭州", "arr": "重庆", "days": "", "priceType": "1"}),
]

for name, params in variants:
    url = "https://gw.flight.qunar.com/api/f/priceCalendar"
    try:
        r = S.get(url, params=params, headers=UA_MB, timeout=20)
        print(f"[{name}] {r.status_code} len={len(r.text)}")
        print(r.text[:1500])
        try:
            j = r.json()
            if isinstance(j, dict) and j.get("data"):
                gf = j["data"].get("gflights") or []
                print("gflights n=", len(gf), "first:", json.dumps(gf[:2], ensure_ascii=False))
        except Exception as e:
            print("  (not plain json:", e, ")")
    except Exception as e:
        print(f"[{name}] ERR {e}")
    print("-" * 70)
