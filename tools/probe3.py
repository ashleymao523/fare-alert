# -*- coding: utf-8 -*-
"""Round-3 probe: extract candidate API endpoints from cached pages."""
import re

files = ["tools/cache/qunar_home.html", "tools/cache/qunar_pc_lowprice_try.html", "tools/cache/ctrip_home.html"]

for path in files:
    print("=" * 20, path, "=" * 20)
    with open(path, encoding="utf-8", errors="ignore") as f:
        html = f.read()

    # script sources
    srcs = sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', html)))
    interesting = [s for s in srcs if re.search(r'flight|price|search|list', s, re.I)]
    print(f"-- scripts({len(srcs)} total, {len(interesting)} interesting):")
    for s in interesting[:30]:
        print("   ", s)

    # keyword contexts
    for kw in ["lowprice", "lowPrice", "LowPrice", "restapi", "/api/", "flight/api"]:
        for m in re.finditer(re.escape(kw), html):
            ctx = html[max(0, m.start() - 70):m.end() + 90].replace("\n", " ")
            print(f"-- ctx[{kw}]:", ctx)
    print()
