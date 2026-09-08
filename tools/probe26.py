# -*- coding: utf-8 -*-
"""Check if ctrip actualtime flight-number page is SSR (has times in HTML)."""
import re
import requests

UA_D = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
s = requests.Session()
fno = "PN6496"
urls = [
    "https://flights.ctrip.com/actualtime/fno/" + fno + ".html",
    "https://www.umetrip.com/mskyweb/fs/fc.do?dep=HGH&arr=CKG&fno=" + fno,
    "https://www.travel-africa.com.cn/...",
]
urls = urls[:2]
for u in urls:
    try:
        r = s.get(u, headers={"User-Agent": UA_D,
                              "Accept-Language": "zh-CN,zh;q=0.9"}, timeout=18)
        times = re.findall(r"[0-9]{2}:[0-9]{2}", r.text)
        has_fno = fno in r.text
        print(u[:60], r.status_code, "len", len(r.text),
              "fno:", has_fno, "times:", times[:8])
    except Exception as e:
        print(u[:60], "ERR", e)
