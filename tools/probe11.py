# -*- coding: utf-8 -*-
"""Round-11 probe: full price fields + student purpose codes."""
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
    return r


r = price_query("2026-09-12", "ADULT")
j = r.json()
items = j.get("data") or []
print("adult trains:", len(items))
first = items[0] if items else {}
print("price keys of first item:")
for k, v in first.items():
    if k == "queryLeftNewDTO":
        continue
    print("  ", k, "=", v)

print()
print("student query:")
r2 = price_query("2026-09-12", "0X00")
try:
    j2 = r2.json()
    items2 = j2.get("data") or []
    print("student trains:", len(items2))
    if items2:
        d = items2[0]["queryLeftNewDTO"]
        print("  first train:", d["station_train_code"], d["from_station_name"], d["to_station_name"], d["start_time"], d["arrive_time"])
        for k, v in items2[0].items():
            if k == "queryLeftNewDTO":
                continue
            print("  ", k, "=", v)
except Exception as e:
    print("  ERR", e, r2.text[:200])


def find(items_, code):
    for it in items_:
        if it["queryLeftNewDTO"]["station_train_code"] == code:
            return it
    return None


adult_d = find(items, "D2222")
student_d = find(items2, "D2222") if "items2" in dir() else None
if adult_d and student_d:
    print()
    print("D2222 price fields, adult vs student:")
    for k in adult_d:
        if k == "queryLeftNewDTO":
            continue
        print(f"  {k}: adult={adult_d[k]} student={student_d.get(k)}")
