# -*- coding: utf-8 -*-
"""v0.95 CLI: one-shot per-offer price backfill.

Re-probes every cached positive booking entry whose offers lack
price_eur (they predate the v0.94 parse), so measured-flight chips
gain their own reference prices immediately instead of riding the
48h TTL rotation. Gentle by design: same keyless endpoint, >=4s
between calls, disk-merge saves never clobber a concurrent worker
round, failed probes keep the old entry.

Usage:
  python -X utf8 tools/backfill_offer_prices.py             # all
  python -X utf8 tools/backfill_offer_prices.py --max 30    # capped
  python -X utf8 tools/backfill_offer_prices.py --routes hangzhou-chongqing
"""
import argparse
import copy
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import requests

from core.booking_fill import backfill_prices
from core.intl import city_iata


def route_iatas_from_cfg(cfg):
    out = {}
    for r in cfg.get("routes") or []:
        rid = (r.get("id") or "").strip()
        fc, tc = r.get("from_city") or "", r.get("to_city") or ""
        fi = (r.get("from_iata") or "").strip().upper() \
            or (city_iata(fc) if fc else "")
        ti = (r.get("to_iata") or "").strip().upper() \
            or (city_iata(tc) if tc else "")
        if rid and fi and ti:
            out[rid] = (fi, ti)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max", type=int, default=0,
                    help="stop after N probes (0 = unlimited)")
    ap.add_argument("--interval", type=float, default=None,
                    help="seconds between live calls (default cfg)")
    ap.add_argument("--routes", default="",
                    help="comma-separated route ids to include")
    args = ap.parse_args()

    with open(os.path.join(REPO, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    ri = route_iatas_from_cfg(cfg)
    if args.routes:
        keep = {x.strip() for x in args.routes.split(",") if x.strip()}
        ri = {k: v for k, v in ri.items() if k in keep}
    if not ri:
        print("no routes resolved (check config.json)")
        return 1
    if args.interval is not None:
        cfg = copy.deepcopy(cfg)
        cfg.setdefault("booking_fill", {})["call_interval"] = \
            args.interval
    print("routes:", ", ".join("%s(%s-%s)" % (k, v[0], v[1])
                                for k, v in ri.items()))
    stats = backfill_prices(
        requests.Session(), cfg.get("network") or {}, cfg,
        os.path.join(REPO, "data"), ri, max_n=args.max,
        log=lambda m: print(m, flush=True))
    print("STATS", json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
