# -*- coding: utf-8 -*-
"""Parallel quick probe: CKG/CTF/TFU airport sites (8s timeout each)."""
import concurrent.futures as cf
import urllib.request
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

CANDS = [
    'https://www.cqa.com.cn/',
    'http://www.cqa.com.cn/',
    'https://www.cdairport.com.cn/',
    'http://www.cdairport.com.cn/',
    'https://www.tfairport.com/',
    'https://www.tfcairport.com/',
]

def probe(u):
    try:
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        r = urllib.request.urlopen(req, timeout=8)
        b = r.read(2048).decode('utf-8', 'replace')
        return 'OK   %s %d len>=%d %r' % (u, r.status, len(b), b[:60])
    except Exception as e:
        return 'FAIL %s %s %s' % (u, type(e).__name__, str(e)[:70])

if __name__ == '__main__':
    import re
    with cf.ThreadPoolExecutor(8) as ex:
        for line in ex.map(probe, CANDS):
            print(line, flush=True)
    html = urllib.request.urlopen(
        urllib.request.Request('http://www.cqa.com.cn/',
                                headers={'User-Agent': 'Mozilla/5.0'}),
        timeout=10).read().decode('utf-8', 'replace')
    print('--- homepage len', len(html))
    for m in sorted(set(re.findall(r'href="([^"]*)"', html))):
        if any(k in m for k in ('flight', 'hb', 'arrive', 'dep', '航班')):
            print('LINK', m)
    for m in sorted(set(re.findall(r'src="([^"]*)"', html))):
        print('JS', m)
