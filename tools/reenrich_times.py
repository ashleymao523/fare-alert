# -*- coding: utf-8 -*-
"""Re-run flight-time enrichment over an existing snapshot (offline).

After a sched-db upgrade (e.g. the v0.32 nextschtime arrival backfill)
this refreshes dep/arr times + time_coverage in data/snapshot.json
WITHOUT any network request or crawl cycle, so the web UI reflects the
new data immediately. Deals keep prices/urls/sources untouched.

Usage: python -X utf8 tools/reenrich_times.py [--dry]
"""
import argparse
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import main as app_main  # noqa: E402

TIME_FIELDS = ("dep_time", "arr_time", "arr_est", "duration_text",
               "time_src", "dep_src", "arr_src", "alt_times",
               "stop_kind", "stop_city", "stop_arr")


def _reset_time_fields(d):
    if d.time_src == "amadeus":
        # Amadeus times are the strongest source; the replay below runs
        # with ama_ready=False, so keep them instead of letting board
        # data overwrite real times (v0.32 review P1)
        return
    d.dep_time = ""
    d.arr_time = ""
    d.arr_est = ""
    d.time_src = ""
    d.dep_src = ""
    d.arr_src = ""
    d.duration_text = ""
    d.stop_kind = ""
    d.stop_city = ""
    d.stop_arr = ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    snap_path = os.path.join(ROOT, "data", "snapshot.json")
    with open(snap_path, encoding="utf-8") as f:
        snap = json.load(f)
    cfg = app_main.load_config(app_main.CONFIG_PATH)
    ama_cfg = (cfg.get("amadeus") or {})
    stats = []
    for r in snap.get("routes") or []:
        raw = r.get("deals") or []
        from core.models import FlightDeal
        deals = [FlightDeal(**{k: v for k, v in m.items()
                               if k in FlightDeal.__dataclass_fields__})
                 for m in raw]
        for d in deals:
            _reset_time_fields(d)
        out = app_main._enrich_flight_times(
            None, {}, r, deals, cfg, ama_cfg, False,
            r.get("window", ["", ""])[0], r.get("window", ["", ""])[1])
        cov = app_main.time_coverage(out)
        stats.append((r.get("id"), len(out), cov))
        if not args.dry:
            by_date = {d.date: d for d in out}
            for m in raw:
                d = by_date.get(m.get("date"))
                if not d:
                    continue
                for k in TIME_FIELDS:
                    if k == "alt_times":
                        m[k] = [{"no": a.get("no"), "dep": a.get("dep"),
                                 "exact": bool(a.get("exact"))}
                                for a in (d.alt_times or [])][:4]
                    else:
                        m[k] = getattr(d, k, "")
            r["time_coverage"] = cov
    for rid, n, cov in stats:
        print("%-16s deals=%-3d dep %d/%d (exact %d) arr real %d est %d miss %d"
              % (rid, n,
                 cov["dep_exact"] + cov["dep_borrow"], cov["total"],
                 cov["dep_exact"],
                 cov["arr_exact"] + cov["arr_borrow"],
                 cov["arr_est"], cov["arr_missing"]))
    if args.dry:
        print("(dry run, snapshot untouched)")
        return 0
    shutil.copyfile(snap_path, "%s.bak-%d" % (snap_path, int(time.time())))
    tmp = snap_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)
    os.replace(tmp, snap_path)
    print("snapshot rewritten (backup saved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
