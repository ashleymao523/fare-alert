# -*- coding: utf-8 -*-
"""Round-12 probe: dig into queryLeftNewDTO price fields."""
import json
import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://kyfw.12306.cn/otn/leftTicketPrice/init",
}
S = requests.Session()
S.trust_env = False


def price_query(date, purpose):
    r = S.get("https://kyfw.12306.cn/otn/leftTicketPrice/query", params={
        "leftTicketDTO.train_date": date,
        "leftTicketDTO.from_station": "HGH",
        "leftTicketDTO.to_station": "CUW",
        "purpose_codes": purpose,
    }, headers=UA, timeout=20)
    return r.json().get("data") or []


adult = price_query("2026-09-12", "ADULT")
student = price_query("2026-09-12", "0X00")

d = adult[0]["queryLeftNewDTO"]
print("== adult first train:", d["station_train_code"])
for k in sorted(d.keys()):
    print(f"   {k} = {d[k]}")

print()
print("== price-ish fields adult vs student (D2222):")
def find(items_, code):
    for it in items_:
        if it["queryLeftNewDTO"]["station_train_code"] == code:
            return it["queryLeftNewDTO"]


a = find(adult, "D2222")
s = find(student, "D2222")
if a and s:
    for k in sorted(a.keys()):
        if a[k] != s.get(k):
            print(f"   {k}: adult={a[k]} | student={s[k]}")
