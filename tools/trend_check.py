# -*- coding: utf-8 -*-
"""Verify premium trend chart elements exist in the rendered DOM dump."""
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

h = open("data/ui_dom.html", encoding="utf-8-sig").read()
m = re.search(r'<svg id=.trendSvg.*?</svg>', h, re.S)
if not m:
    print("FAIL trend svg missing")
    sys.exit(1)
svg = m.group(0)

weekend_bands = svg.count("rgba(23,32,64,0.03)")

# threshold / min values from the rendered chips (data-aware checks)
th_m = re.search(r"\u5fc3\u7406\u4ef7\u4f4d \u00a5(\d+)", svg)
mn_m = re.search(r"\u6700\u4f4e \u00a5(\d+)", svg)
th_val = int(th_m.group(1)) if th_m else None
mn_val = int(mn_m.group(1)) if mn_m else None
below_days = bool(th_val is not None and mn_val is not None and mn_val < th_val)
checks = {
    "smooth path (C segments)": " C " in svg,
    "gradient defs": ("areaGrad" in svg) and ("lineGrad" in svg),
    "area fill uses gradient": re.search(r"url\(#areaGrad\)", svg) is not None,
    "line stroke uses gradient": re.search(r"url\(#lineGrad\)", svg) is not None,
    "weekend bands >= 10": weekend_bands >= 10,
    "threshold dashed line": svg.count("#dc2626") >= 1,
    "threshold label chip": svg.count("rgba(220,38,38,0.10)") == 1,
    "below-threshold glow dots (data-aware)": ("rgba(22,163,74,0.16)" in svg) == below_days,
    "min pulse animation": 'animate attributeName' in svg,
    "min pill badge": 'rx="10.5"' in svg,
    "hover crosshair": "trendCross" in svg,
    "hover dot": "trendDot" in svg,
    "y axis yen labels": len(re.findall(r'text-anchor="end">\u00a5', svg)) >= 4,
    "tooltip div rendered": 'class="trend-tip"' in h,
}
bad = 0
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
    bad += 0 if v else 1
print("weekend bands:", weekend_bands)
print("threshold:", th_val, "min:", mn_val, "below_days:", below_days)
sys.exit(1 if bad else 0)
