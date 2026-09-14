# -*- coding: utf-8 -*-
"""Daily per-route KPI archive for the weekly insight report (M4).

Every run_once appends one compact record per route per day (same-day
re-runs overwrite, keeping the latest). Only aggregates are stored so the
file stays tiny; every weekly-report number can be recomputed from here.
"""
import datetime as dt
import json
import os

MAX_DAYS = 180  # keep ~6 months of history
NON_REAL_SOURCES = ("nearby-ref", "interp")


def load_history(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc, dict) and isinstance(doc.get("days"), dict):
                return doc
        except Exception:
            pass
    return {"days": {}}


def _route_metrics(route):
    """Compute one day's KPIs from a snapshot route block."""
    deals = [d for d in (route.get("deals") or [])
             if d.get("source") not in NON_REAL_SOURCES
             and isinstance(d.get("total_price"), (int, float))]
    if not deals:
        return None
    totals = [float(d["total_price"]) for d in deals]
    best = min(deals, key=lambda d: d["total_price"])
    m = {
        "from_city": route.get("from_city", ""),
        "to_city": route.get("to_city", ""),
        "threshold": route.get("threshold_total"),
        "cheapest_total": round(min(totals), 1),
        "avg_total": round(sum(totals) / len(totals), 1),
        "days_below": int(route.get("days_below") or 0),
        "best_date": best.get("date"),
        "n_deals": len(deals),
    }
    # v0.45: archive dep-time coverage so the sources tab can chart how
    # exact-departure coverage grows day over day (goal-1 progress curve).
    cov = route.get("time_coverage") or {}
    if cov.get("total"):
        m["cov"] = {"dx": int(cov.get("dep_exact") or 0),
                    "db": int(cov.get("dep_borrow") or 0),
                    "dm": int(cov.get("dep_missing") or 0)}
    return m


def coverage_trend(history, days=30):
    """v0.45: daily dep-time coverage ratio series (pure, CI-testable).

    Aggregates per-route cov blocks per archived day. Days without cov
    (pre-v0.45 archives) are skipped rather than plotted as 0%. Returns
    [{date, de, db, dm, tot, pct}] ascending, capped to the last `days`.
    """
    out = []
    for day, rec in sorted((history.get("days") or {}).items()):
        de = db = dm = 0
        for m in ((rec.get("routes") or {}).values()):
            c = m.get("cov")
            if not c:
                continue
            de += int(c.get("dx") or 0)
            db += int(c.get("db") or 0)
            dm += int(c.get("dm") or 0)
        tot = de + db + dm
        if not tot:
            continue
        out.append({"date": day, "de": de, "db": db, "dm": dm,
                    "tot": tot, "pct": round(de * 100.0 / tot, 1)})
    return out[-days:] if days else out


def day_drops(history, pct=15.0, abs_yuan=50.0):
    """v0.55: per-route window-min change between the two most recent
    archived days (pure, CI-testable).

    A drop is "sharp" only when it clears BOTH gates - relative -pct%
    and absolute -abs_yuan - so a ¥20 dip on a ¥150 ticket never fires
    and a 16% dip on an ¥80 ticket never fires either. Same-day re-runs
    are idempotent (append_history overwrites the day)."""
    days = sorted((history.get("days") or {}).items())
    if len(days) < 2:
        return []
    (d0, r0), (d1, r1) = days[-2], days[-1]
    out = []
    for rid, m in (r1.get("routes") or {}).items():
        pm = (r0.get("routes") or {}).get(rid)
        if not pm:
            continue
        t, p = m.get("cheapest_total"), pm.get("cheapest_total")
        if not all(isinstance(x, (int, float)) and x > 0 for x in (t, p)):
            continue
        delta = round(float(t) - float(p), 1)
        rel = round((float(t) - float(p)) * 100.0 / float(p), 1)
        out.append({"route_id": rid, "date": d1, "prev_date": d0,
                    "from_city": m.get("from_city") or "",
                    "to_city": m.get("to_city") or "",
                    "today": round(float(t), 1), "prev": round(float(p), 1),
                    "delta": delta, "pct": rel,
                    "sharp": (delta < 0 and -rel >= float(pct)
                              and -delta >= float(abs_yuan))})
    return out


def append_history(snapshot, path):
    """Archive today's per-route KPIs (same day + route id overwrites)."""
    day = dt.date.today().isoformat()
    doc = load_history(path)
    day_rec = doc["days"].setdefault(day, {"routes": {}})
    routes = day_rec.setdefault("routes", {})
    n = 0
    for route in (snapshot or {}).get("routes") or []:
        m = _route_metrics(route)
        if m:
            routes[route.get("id", "route")] = m
            n += 1
    cutoff = (dt.date.today() - dt.timedelta(days=MAX_DAYS)).isoformat()
    for d in [k for k in doc["days"] if k < cutoff]:
        doc["days"].pop(d, None)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
    except Exception:
        raise
    return n
