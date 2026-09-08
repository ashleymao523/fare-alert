# -*- coding: utf-8 -*-
"""Round-5 probe: mine bundles for API paths."""
import re

targets = ["tools/cache/qbundle0.js", "tools/cache/qbundle1.js", "tools/cache/qunar_lowflight.html"]

api_pat = re.compile(r'["\'](/[A-Za-z0-9_/.-]{4,80})["\']')
kw_pat = re.compile(r'(lowPrice|lowprice|LowPrice|低价)')

for path in targets:
    print("=" * 20, path, "=" * 20)
    with open(path, encoding="utf-8", errors="ignore") as f:
        s = f.read()
    apis = sorted(set(m.group(1) for m in api_pat.finditer(s)))
    hits = [a for a in apis if re.search(r'api|json|price|Price|flight', a)]
    print("-- api-like paths:")
    for a in hits[:60]:
        print("   ", a)
    print("-- lowprice contexts:")
    for m in list(kw_pat.finditer(s))[:10]:
        print("   ...", s[max(0, m.start() - 100):m.end() + 150].replace("\n", " "))
    print()
