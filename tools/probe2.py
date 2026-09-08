# -*- coding: utf-8 -*-
"""Round-2 probe: download pages, extract script bundles for endpoint discovery."""
import os
import re
import requests

UA_MB = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
UA_PC = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

os.makedirs("tools/cache", exist_ok=True)
S = requests.Session()
S.trust_env = False

pages = {
    "qunar_home": ("https://m.flight.qunar.com/", UA_MB),
    "qunar_pc_lowprice_try": ("https://flight.qunar.com/site/oneway/list?searchManuType=1&depCity=%E6%9D%AD%E5%B7%9E&arrCity=%E9%87%8D%E5%BA%86&goDate=2026-09-15&fromNoCity=true", UA_PC),
    "ctrip_home": ("https://m.ctrip.com/", UA_MB),
}

for name, (url, ua) in pages.items():
    try:
        r = S.get(url, headers=ua, timeout=20)
        path = f"tools/cache/{name}.html"
        with open(path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(r.text)
        print(f"[{name}] {r.status_code} saved len={len(r.text)} -> {path}")
    except Exception as e:
        print(f"[{name}] ERR {type(e).__name__}: {e}")
