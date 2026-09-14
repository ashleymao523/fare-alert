# -*- coding: utf-8 -*-
# v0.76 recon archive: can the grey "cha-jia" calendar dates be point-
# queried headlessly? Verdict: NO (2026-09-14).
#   - touchInnerList/touchInterList need Bella signature + fingerprint:
#     every param shape tried here returns code 1999; headless Edge dom
#     dumps show no prices; even the in-app real browser shows "no
#     flights" on a date the calendar itself prices (2026-09-16).
#   - Grey dates are NOT sold out: the server simply has no cached floor
#     price yet. Filling them = Amadeus per-date offers (needs key) or
#     the point-fill cache (POST /api/point-fill from a real browser).
import re, sys, requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
Q = chr(34)
UA = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'}
LIST_URL = ('https://m.flight.qunar.com/ncs/page/flightlist?depCity=%E6%9D%AD%E5%B7%9E'
            '&arrCity=%E9%87%8D%E5%BA%86&goDate=2026-10-13&from=touch_index_search')
h = requests.get(LIST_URL, headers=UA, timeout=20).text
print('list page bytes:', len(h))
pat = re.compile('src=' + Q + '([^'+ Q + ']+[.]js[^'+ Q + ']*)' + Q)
srcs = []
for m in pat.finditer(h):
    u = m.group(1)
    if u.startswith('//'): u = 'https:' + u
    elif u.startswith('/'): u = 'https://m.flight.qunar.com' + u
    srcs.append(u)
srcs = sorted(set(srcs))
print('scripts:', len(srcs))
for s in srcs[:12]: print('  JS:', s)
upat = re.compile(r'https?://[A-Za-z0-9.\-]*qunar[A-Za-z0-9.\-]*/[A-Za-z0-9/_.\-]{4,80}')
rpat = re.compile(r'/[A-Za-z0-9_\-]{2,30}/(?:api|search|flight)[A-Za-z0-9_/\-]{2,60}')
seen = set()
for s in srcs[:12]:
    try:
        body = requests.get(s, headers=UA, timeout=20).text
    except Exception as e:
        print('  FAIL', s, type(e).__name__); continue
    print('  bundle', s[-56:], len(body))
    for p in upat.findall(body) + rpat.findall(body):
        if p not in seen: seen.add(p)
print('api-ish paths:')
for p in sorted(seen)[:80]: print(' ', p)
