#!/usr/bin/env python3
"""v1.14.1 ops tool: one-shot precise refill of cabin time-gap dates.

The patrol's k//2 budget split repairs a few gap dates per 30-min
round; this drains the WHOLE gap backlog in one run through the
exact same data path (booking LOWEST_PRICE BUSINESS -> rows ->
_cabin_absorb with push off). Only cabin_history.json moves - no
state.json writes, no pushes, atomic history write keeps a live
worker safe.

Usage (repo root):
  python -X utf8 tools/cabin_refill.py --dry      # list gaps only
  python -X utf8 tools/cabin_refill.py            # refill every leg
  python -X utf8 tools/cabin_refill.py --max 40   # cap dates per leg
"""
import argparse
import datetime as dt
import sys
import time

sys.path.insert(0, ".")

from core.alerts import tax_amount
from core.booking_fill import _resolve_fx, fetch_lowest
from core.booking_fill import bump_fingerprint, warm_session
from core.cabin_monitor import booking_cabin_rows
from core.cabin_monitor import load_config as cabin_cfg_load
from core.cabin_monitor import load_history as cabin_history_load
from core.cabin_monitor import patrol_legs, time_gap_dates
from core.config import load_config
from core.intl import city_iata
from core.patrol import _SilentLog
from main import DATA_DIR, _cabin_absorb, make_session


def main() -> int:
    ap = argparse.ArgumentParser(
        description="One-shot precise refill of cabin time-gap dates.")
    ap.add_argument("--max", type=int, default=20,
                    help="max gap dates refilled per leg (default 20)")
    ap.add_argument("--dry", action="store_true",
                    help="only list gap dates, no network calls")
    args = ap.parse_args()

    cfg = load_config("config.json")
    cw = cabin_cfg_load(cfg)
    if not cw.get("enabled"):
        print("cabin watch disabled in config")
        return 1
    legs = patrol_legs(cw, cfg.get("routes") or [])
    if not legs:
        print("no independent patrol legs (watch_from_cities empty?)")
        return 1

    today = dt.date.today()
    date_from = (today + dt.timedelta(days=1)).isoformat()
    date_to = (today + dt.timedelta(days=60)).isoformat()
    hist = cabin_history_load(DATA_DIR)

    plan = []
    for leg in legs:
        hid = "leg-{fc}-{tc}".format(
            fc=leg["from_city"], tc=leg["to_city"])
        gaps = time_gap_dates(hist, hid, date_from, date_to)
        gaps = gaps[:max(0, args.max)]
        plan.append((leg, hid, gaps))
        print("{fc}->{tc}: {n} gap date(s){tail}".format(
            fc=leg["from_city"], tc=leg["to_city"], n=len(gaps),
            tail="" if not gaps else " " + ",".join(gaps)))
    total = sum(len(g) for _, _, g in plan)
    if args.dry:
        print("dry-run: {n} gap date(s) total, no calls made".format(
            n=total))
        return 0
    if not total:
        print("no gaps - nothing to refill")
        return 0

    session = make_session(cfg)
    tax_amt = tax_amount(cfg.get("tax", {}))
    net = cfg.get("network", {})
    interval = float((cfg.get("booking_fill") or {}).get(
        "call_interval", 4.0) or 4.0)
    n_rows = 0
    n_hit = 0
    errs = 0
    n_trans = 0
    for leg, hid, gaps in plan:
        fi = city_iata(leg["from_city"])
        ti = city_iata(leg["to_city"])
        if not (fi and ti):
            errs += 1
            print("  SKIP {fc}->{tc}: iata unknown".format(
                fc=leg["from_city"], tc=leg["to_city"]))
            continue
        fx = _resolve_fx(session, cfg, DATA_DIR)
        done = 0
        for i, d in enumerate(gaps):
            if i:
                time.sleep(interval)
            try:
                got = fetch_lowest(session, net, fi, ti, d,
                                   offer_limit=8, cabin_class="BUSINESS")
            except Exception as e:
                errs += 1
                print("  {d} ERR {e}".format(d=d, e=e))
                got = None
            if got is None:
                # non-200 / transport: transient (throttle) - a retry
                # minutes later often prices the date, do NOT read
                # this as "confirmed empty".
                n_trans += 1
                print("  {d} transient (throttled?)".format(d=d))
                continue
            if got.get("throttled"):
                # v1.15: explicit 429 - circuit-break this leg (the
                # limiter stays fed while we keep calling) and leave
                # the rest for a later rerun; fingerprint rotated so
                # the next run wears a fresh identity.
                n_trans += 1
                print("  {d} 429 throttled - circuit break, "
                      "rerun later for the rest".format(d=d))
                bump_fingerprint()
                session = make_session(cfg)
                warm_session(session, net)
                break
            if got.get("no_data"):
                print("  {d} no offers (server-confirmed)".format(d=d))
                continue
            rows = booking_cabin_rows(d, got, tax_amt, fx)
            if rows:
                done += 1
                n_rows += len(rows)
                # push off + empty state: only cabin_history.json moves
                _cabin_absorb(cw, leg, hid, rows, cfg, {},
                              _SilentLog(), False, source="booking")
        n_hit += done
        print("{fc}->{tc}: {done}/{n} gap dates got business offers".format(
            fc=leg["from_city"], tc=leg["to_city"],
            done=done, n=len(gaps)))
    print("refill done: {h}/{t} dates priced, {r} rows absorbed, "
          "{v} transient, {e} errors".format(
              h=n_hit, t=total, r=n_rows, v=n_trans, e=errs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
