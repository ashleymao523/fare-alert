# -*- coding: utf-8 -*-
"""Round-10 probe: 12306 stations + leftTicket + price query."""
import json
import re
import requests

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.trust_env = False

# 1. stations
r = S.get("https://kyfw.12306.cn/otn/resources/js/framework/station_name.js", headers=UA, timeout=20)
m = re.search(r"var station_names ='([^']+)'", r.text)
stations = {}
for ent in m.group(1).split("@"):
    if not ent:
        continue
    p = ent.split("|")
    stations[p[1]] = p[2]
for name in ["杭州", "杭州东", "杭州西", "杭州南", "重庆", "重庆北", "重庆西"]:
    print(name, "->", stations.get(name))

# 2. left ticket query
def left_query(from_st, to_st, date, purpose="ADULT"):
    url = "https://kyfw.12306.cn/otn/leftTicket/query"
    params = {
        "leftTicketDTO.train_date": date,
        "leftTicketDTO.from_station": from_st,
        "leftTicketDTO.to_station": to_st,
        "purpose_codes": purpose,
    }
    r = S.get(url, params=params, headers=UA, timeout=20)
    return r

hz = stations["杭州东"]
cq = stations["重庆北"]
try:
    r = left_query(hz, cq, "2026-09-12")
    print("[leftTicket]", r.status_code, "len", len(r.text))
    j = r.json()
    print(json.dumps(j, ensure_ascii=False)[:1200])
except Exception as e:
    print("[leftTicket] ERR", type(e).__name__, e)
    if "r" in dir():
        print(r.text[:300])

# 3. price query variants
for path in [
    "https://kyfw.12306.cn/otn/leftTicketPrice/query",
    "https://kyfw.12306.cn/otn/leftTicketPrice/queryAll",
]:
    try:
        r = S.get(path, params={
            "leftTicketDTO.train_date": "2026-09-12",
            "leftTicketDTO.from_station": hz,
            "leftTicketDTO.to_station": cq,
            "purpose_codes": "ADULT",
        }, headers=UA, timeout=20)
        print("[price]", path.split("/")[-1], r.status_code, r.text[:600])
    except Exception as e:
        print("[price]", path.split("/")[-1], "ERR", e)
