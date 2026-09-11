# -*- coding: utf-8 -*-
# v0.35 probe: does the HGH board API take a date parameter? Read-only,
# reads the public flight page + its JS assets only, never the board API.
# CONCLUSION (2026-09-11): the board endpoint has NO date parameter; the
# keywords field only feeds the flight-number search box, and rows carry
# fi_date but the API only serves "today". So dow coverage can ONLY accrete
# day-by-day via the worker -- exactly what v0.34 autostart enables.
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
PAGE = "https://www.hzairport.com/flight/index.html"


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")


html = fetch(PAGE)
print("page bytes:", len(html))

srcs = []
for m in re.finditer(r'src=["\']([^"\']+\.js[^"\']*)["\']', html):
    u = m.group(1)
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/"):
        u = "https://www.hzairport.com" + u
    srcs.append(u)
print("js refs:", len(srcs))

KEYS = ("fi_date", "hbh", "_import", "riqi", "rq=", "dq=", "date=")
for u in srcs[:12]:
    try:
        body = fetch(u)
    except Exception as e:
        print("JS FAIL", u, type(e).__name__, str(e)[:80])
        continue
    hits = []
    for kw in KEYS:
        i = body.find(kw)
        if i >= 0:
            hits.append((kw, body[max(0, i - 70):i + 110].replace("\n", " ")))
    if hits:
        print("== ", u, len(body))
        for kw, ctx in hits[:6]:
            print("   [%s] %s" % (kw, ctx))

for kw in KEYS:
    i = html.find(kw)
    if i >= 0:
        print("page-inline [%s] %s" % (kw, html[max(0, i - 70):i + 110].replace("\n", " ")))
