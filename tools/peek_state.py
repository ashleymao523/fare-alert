# -*- coding: utf-8 -*-
import json

s = json.load(open("data/snapshot.json", encoding="utf-8"))
for r in s.get("routes", []):
    rid = r.get("id")
    deals = r.get("deals", [])
    src = {}
    for f in deals:
        src[f.get("source", "?")] = src.get(f.get("source", "?"), 0) + 1
    dates = sorted(set(f["date"] for f in deals))
    n_with_price = 0
    n_ref = 0
    for f in deals:
        if f.get("source") == "nearby-ref":
            n_ref += 1
    print(rid, "n_deal_dates:", len(dates), "sources:", src, "ref_count:", n_ref)
    print("  last8:", dates[-8:] if dates else [])
