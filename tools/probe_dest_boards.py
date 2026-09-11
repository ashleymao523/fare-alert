# -*- coding: utf-8 -*-
"""Probe destination-airport schedule boards (read-only, archived probe).

v0.22 noted cqairport.com is parked. This probe checks Zhengzhou (CGO)
and Chongqing (CKG) candidates for a public flight-board API that could
fill arrival times from the destination side.
"""
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CANDIDATES = [
    "https://www.zzairport.com.cn/",
    "http://www.zzairport.com.cn/",
    "https://www.zzhairport.com/",
    "https://www.cqa.com.cn/",
    "https://www.chongqingairport.com.cn/",
    "http://www.cqairport.com/",
]

for u in CANDIDATES:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        r = urllib.request.urlopen(req, timeout=8)
        body = r.read(4096).decode("utf-8", "replace")
        print("OK  ", u, r.status, len(body), "first-bytes:", body[:80].replace(chr(10), " "))
    except Exception as e:
        print("FAIL", u, type(e).__name__, str(e)[:90])

# follow the JS redirect on cqairport.com if it answers again
try:
    req = urllib.request.Request("http://www.cqairport.com/",
                                 headers={"User-Agent": "Mozilla/5.0"})
    b = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    print("cqairport body:", repr(b[:400]))
except Exception as e:
    print("cqairport follow-up failed:", type(e).__name__, str(e)[:120])
