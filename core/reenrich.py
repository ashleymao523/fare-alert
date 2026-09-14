# -*- coding: utf-8 -*-
"""v0.41: offline snapshot time re-enrichment (core).

The sched board db grows one weekday per day while the crawler runs, but
snapshot deal times were only refreshed on the next successful crawl.
This module replays _enrich_flight_times over the EXISTING snapshot with
the CURRENT db - zero network, zero new price requests - so the UI picks
up newly deposited board times daily (wired into the 09:00 patrol).

tools/reenrich_times.py stays as the CLI wrapper over this core.
"""
import json
import glob
import os
import shutil
import time

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


def reenrich_snapshot(base_dir, dry=False, log=None):
    """Rebuild deal times in <base_dir>/data/snapshot.json from the
    current flight_sched_db.json. Prices/urls/sources stay untouched.
    Returns {"routes": N, "dep_covered": X, "dep_total": Y,
             "changed": bool, "per_route": [...]}. Missing snapshot ->
    routes=0 (not an error: a fresh install has nothing to replay)."""
    import sys
    root = os.path.abspath(base_dir)
    if root not in sys.path:
        sys.path.insert(0, root)
    import main as app_main  # noqa: E402
    from core.models import FlightDeal  # noqa: E402

    snap_path = os.path.join(root, "data", "snapshot.json")
    try:
        with open(snap_path, encoding="utf-8") as f:
            snap = json.load(f)
    except FileNotFoundError:
        return {"routes": 0, "dep_covered": 0, "dep_total": 0,
                "changed": False, "per_route": []}

    # isolation: point main's globals at THIS base_dir (tests pass a tmp
    # dir; production passes the repo dir, which is already the default)
    old_data_dir, old_cfg_path = app_main.DATA_DIR, app_main.CONFIG_PATH
    app_main.DATA_DIR = os.path.join(root, "data")
    app_main.CONFIG_PATH = os.path.join(root, "config.json")
    try:
        cfg = app_main.load_config(app_main.CONFIG_PATH)
    except Exception:
        cfg = {}
    ama_cfg = ((cfg.get("sources") or {}).get("amadeus")) or {}

    stats = []
    changed = False
    try:
        for r in snap.get("routes") or []:
            raw = r.get("deals") or []
            deals = [FlightDeal(**{k: v for k, v in m.items()
                                   if k in FlightDeal.__dataclass_fields__})
                     for m in raw]
            for d in deals:
                _reset_time_fields(d)
            win = r.get("window") or ["", ""]
            out = app_main._enrich_flight_times(
                None, {}, r, deals, cfg, ama_cfg, False,
                win[0], win[1])
            # v0.42: numbered-but-unboarded deals (codeshare strings) also
            # deserve the day's same-route reference departures.
            out = app_main._attach_alt_times(
                out, r.get("to_city", ""),
                app_main.load_sched_db(app_main.DATA_DIR))
            cov = app_main.time_coverage(out)
            stats.append({"id": r.get("id"), "deals": len(out), "cov": cov})
            if dry:
                continue
            # sample BEFORE the write-back mutates raw (same dicts!)
            alt_before = {m.get("date"): (m.get("alt_times") or [])
                          for m in raw}
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
            # v0.42: alt_times (codeshare reference departures) moves
            # without changing coverage counts - compare those too, else
            # the widened _attach_alt_times never persists.
            alt_after = {d.date: (d.alt_times or []) for d in out}
            if (r.get("time_coverage") != cov
                    or any(alt_after.get(k) != v
                           for k, v in alt_before.items())):
                changed = True
            r["time_coverage"] = cov
    finally:
        app_main.DATA_DIR = old_data_dir
        app_main.CONFIG_PATH = old_cfg_path

    write_error = ""
    if not dry and stats and changed:
        # only touch disk when coverage actually moved; the rolling
        # .bak-* retention keeps the newest 3 so the daily patrol
        # cannot pile up unlimited backups (v0.41 review P2)
        try:
            baks = sorted(glob.glob(snap_path + ".bak-*"))
            shutil.copyfile(snap_path, "%s.bak-%d"
                            % (snap_path, int(time.time())))
            for old in baks[:-2]:       # + the one just made = 3 kept
                try:
                    os.remove(old)
                except OSError:
                    pass
            tmp = snap_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snap, f, ensure_ascii=False)
            os.replace(tmp, snap_path)
        except Exception as e:
            write_error = str(e)[:160]
            if log:
                log.warning("reenrich snapshot write failed: %s" % e)
    dep_c = sum(s["cov"]["dep_exact"] + s["cov"]["dep_borrow"]
                for s in stats)
    dep_t = sum(s["cov"]["total"] for s in stats)
    out = {"routes": len(stats), "dep_covered": dep_c,
           "dep_total": dep_t, "changed": changed,
           "per_route": [{"id": s["id"], "deals": s["deals"],
                          "dep_covered": s["cov"]["dep_exact"]
                          + s["cov"]["dep_borrow"],
                          "dep_total": s["cov"]["total"]}
                         for s in stats]}
    if write_error:
        out["write_error"] = write_error
    return out
