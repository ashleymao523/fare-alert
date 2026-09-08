# -*- coding: utf-8 -*-
"""Round-6 probe: parameter shapes for priceCalendar / touchInnerList."""

with open("tools/cache/qbundle0.js", encoding="utf-8", errors="ignore") as f:
    s = f.read()

for kw in ["priceCalendar", "touchInnerList", "getAsyncPrice"]:
    print("=" * 25, kw, "=" * 25)
    start = 0
    for _ in range(4):
        i = s.find(kw, start)
        if i < 0:
            break
        start = i + 1
        print("...", s[max(0, i - 450):i + 450].replace("\n", " "))
        print("-" * 80)
