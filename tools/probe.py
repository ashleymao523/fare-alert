# -*- coding: utf-8 -*-
"""Round-1 probe: reachability of candidate data sources from this machine."""
import time
import requests

UA_PC = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
UA_MB = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

S = requests.Session()
S.trust_env = False  # direct connection, ignore system proxy


def probe(name, url, headers=None, timeout=12):
    try:
        r = S.get(url, headers=headers or UA_MB, timeout=timeout)
        body = r.text[:180].replace("\n", " ")
        print(f"[{name}] {r.status_code} {r.headers.get('content-type', '')} len={len(r.content)} :: {body}")
    except Exception as e:
        print(f"[{name}] ERR {type(e).__name__}: {e}")


targets = [
    ("ctrip-m", "https://m.ctrip.com/", UA_MB),
    ("ctrip-pc-list", "https://flights.ctrip.com/itinerary/oneway/hgh-ckg?depdate=2026-09-15", UA_PC),
    ("qunar-m", "https://m.flight.qunar.com/", UA_MB),
    ("qunar-pc", "https://flight.qunar.com/", UA_PC),
    ("12306-station-js", "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js", UA_PC),
    ("westair", "https://www.westair.cn/", UA_PC),
    ("loongair", "https://www.loongair.cn/", UA_PC),
]

for n, u, h in targets:
    probe(n, u, h)
    time.sleep(0.6)
