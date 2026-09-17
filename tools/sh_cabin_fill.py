#!/usr/bin/env python3
"""v1.18 ops tool: one-shot Shanghai-board cabin time fill.

The patrol round fills a bounded slice (max 4 fnos x 2 offsets);
this drains the WHOLE backlog in one run through the exact same
data path (shanghaiairport.com official board -> exact in-window
obs rewrites + dow deposits). Same global daily cap applies, so a
manual run can never bust the red line.

Usage (repo root):
  python -Xutf8 tools/sh_cabin_fill.py --dry   # targets only
  python -Xutf8 tools/sh_cabin_fill.py         # fill + deposit
  python -Xutf8 tools/sh_cabin_fill.py --max 8
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, ".")

from core.cabin_monitor import load_history as cabin_history_load
from core.config import load_config
from core.sched_board import _atomic_write, load_sched_db
from core.sh_board import (apply_exact_times, dow_targets,
                           exact_targets, fetch_flight,
                           merge_sh_rows)
from main import DATA_DIR, make_session


def main() -> int:
    ap = argparse.ArgumentParser(
        description="One-shot Shanghai-board cabin time fill.")
    ap.add_argument("--max", type=int, default=4,
                    help="max flight numbers per run (default 4)")
    ap.add_argument("--dry", action="store_true",
                    help="only list targets, no network calls")
    args = ap.parse_args()

    hist = cabin_history_load(DATA_DIR)
    today = dt.date.today()
    ex = exact_targets(hist, today)
    db = load_sched_db(DATA_DIR)
    dow = dow_targets(hist, db, max_fnos=args.max)
    print("exact-window targets (today/tomorrow rows):")
    for t in ex[:20]:
        print("  {d} {f} {fc}->{tc}".format(
            d=t["date"], f=t["fno"], fc=t["from_city"],
            tc=t["to_city"]))
    print("dow-deposit targets (missing weekdays):")
    for t in dow:
        print("  {f} dir={dir} needs dows {ws}".format(
            f=t["fno"], dir=t["direction"],
            ws=",".join(t["dows"])))
    if args.dry:
        return 0

    cfg = load_config("config.json")
    session = make_session(cfg)
    net = cfg.get("network", {})
    plan = []
    seen = set()
    for t in ex:
        k = (t["fno"], t["direction"])
        if k not in seen:
            seen.add(k)
            plan.append(k)
    for t in dow:
        k = (t["fno"], t["direction"])
        if k not in seen:
            seen.add(k)
            plan.append(k)
    plan = plan[:args.max]
    exact = 0
    changed = False
    capped = False
    for fno, direction in plan:
        if capped:
            break
        for off in (0, 1):
            try:
                rows, how = fetch_flight(
                    session, net, fno, direction, off, DATA_DIR)
            except Exception as e:
                print("  {f} off{o}: FAIL {e}".format(
                    f=fno, o=off, e=str(e)[:80]))
                continue
            if how == "capped":
                print("  daily cap reached, stopping")
                capped = True
                break
            if rows:
                exact += apply_exact_times(hist, rows)
                changed = merge_sh_rows(db, rows) or changed
            print("  {f} dir{d} off{o}: {n} row(s) [{h}]".format(
                f=fno, d=direction, o=off, n=len(rows), h=how))
    if exact:
        _atomic_write(os.path.join(DATA_DIR, "cabin_history.json"),
                      hist)
    if changed:
        import time as _t
        db["updated"] = _t.time()
        _atomic_write(os.path.join(
            DATA_DIR, "flight_sched_db.json"), db)
    print("exact upgraded: {e}, dow deposited: {c}".format(
        e=exact, c=changed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
