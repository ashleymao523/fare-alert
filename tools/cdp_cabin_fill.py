#!/usr/bin/env python3
"""v1.27 ops tool: real-browser precise business-cabin refill.

Drives ONE headed Edge/Chrome over CDP through the qunar touch list
with the cabin filter applied (筛选 -> 舱位 -> 公务/头等舱 -> 确定,
live-verified 2026-09-17) and deposits the mined cards into the
point-fill cache with the cabin tag - the cabin watch absorbs them
on its next patrol round. This is the PRECISION source for dates the
keyless booking gateway (currently 429-blocked) cannot answer.

Usage (repo root):
  python -Xutf8 tools/cdp_cabin_fill.py --dry        # plan only
  python -Xutf8 tools/cdp_cabin_fill.py --smoke      # 1 fixed target
  python -Xutf8 tools/cdp_cabin_fill.py              # gap refill
  python -Xutf8 tools/cdp_cabin_fill.py --max 4
"""
import argparse
import datetime as dt
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

from core.cabin_monitor import load_config as cabin_cfg_load
from core.cabin_monitor import load_history as cabin_history_load
from core.cabin_monitor import patrol_legs, time_gap_dates
from core.cdp_cabin import capture_batch
from core.config import load_config
from main import DATA_DIR


def main() -> int:
    ap = argparse.ArgumentParser(
        description="CDP real-browser business-cabin precise refill.")
    ap.add_argument("--max", type=int, default=4,
                    help="max gap dates per leg (default 4)")
    ap.add_argument("--dry", action="store_true",
                    help="list targets only, no browser launch")
    ap.add_argument("--smoke", action="store_true",
                    help="one fixed target (北京->上海 tomorrow), "
                         "ignores the watch config")
    args = ap.parse_args()

    today = dt.date.today()
    targets = []
    if args.smoke:
        targets.append({"from_city": "北京", "to_city": "上海",
                        "date": (today + dt.timedelta(days=1)
                                 ).isoformat()})
    else:
        cfg = load_config("config.json")
        cw = cabin_cfg_load(cfg)
        if not cw.get("enabled"):
            print("cabin watch disabled in config")
            return 1
        legs = patrol_legs(cw, cfg.get("routes") or [])
        if not legs:
            print("no patrol legs (watch_from_cities empty?)")
            return 1
        hist = cabin_history_load(DATA_DIR)
        d_from = (today + dt.timedelta(days=1)).isoformat()
        d_to = (today + dt.timedelta(days=60)).isoformat()
        for leg in legs:
            hid = "patrol-{fc}-{tc}".format(fc=leg["from_city"],
                                            tc=leg["to_city"])
            gaps = time_gap_dates(hist, hid, d_from, d_to)[:max(
                0, args.max)]
            for g in gaps:
                targets.append({"from_city": leg["from_city"],
                                "to_city": leg["to_city"],
                                "date": g})
    if not targets:
        print("no targets - nothing to do")
        return 0
    for t in targets:
        print("target {fc}->{tc} {d}".format(
            fc=t["from_city"], tc=t["to_city"], d=t["date"]))
    if args.dry:
        print("dry-run: {n} target(s)".format(n=len(targets)))
        return 0
    t0 = time.time()
    n = capture_batch({}, DATA_DIR, targets, log=print)
    print("stored {n} date row(s) in {s:.0f}s".format(
        n=n, s=time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
