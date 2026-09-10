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
    return {
        "from_city": route.get("from_city", ""),
        "to_city": route.get("to_city", ""),
        "threshold": route.get("threshold_total"),
        "cheapest_total": round(min(totals), 1),
        "avg_total": round(sum(totals) / len(totals), 1),
        "days_below": int(route.get("days_below") or 0),
        "best_date": best.get("date"),
        "n_deals": len(deals),
    }


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
