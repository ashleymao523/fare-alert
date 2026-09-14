# -*- coding: utf-8 -*-
# v0.76: 精点补查缓存 (point-fill cache).
#
# Recon conclusions (2026-09-14, evidence in tools/point_probe.py):
# - qunar low-price calendar leaves dates unpriced server-side; those
#   dates are NOT sold out and NOT a crawler bug - the gateway just has
#   no cached floor price yet.
# - the per-date list API (touchInnerList) is Bella-signed + fingerprint
#   gated: plain POSTs, headless dumps and an embedded real browser all
#   get the same uniform 1999 rejection -> no keyless automated point
#   query today.
#
# Gap dates therefore fill via two tracks:
#   track A (auto):  Amadeus per-date offers (_cached_fill_offers).
#   track B (cache): THIS module - point-queried rows captured in a real
#     browser (bookmarklet / agent / manual) persist here with a TTL and
#     replay over reference-only rows on every crawl. Real rows win.
from __future__ import annotations

import datetime as _dt
import json
import os
import time

CACHE_NAME = "point_fill_cache.json"
POINT_TTL = 48 * 3600          # captured price stays fresh for 2 days
POINT_SOURCE = "point-fill"
MAX_ROWS_PER_ROUTE = 400       # 60d window x out+ret: huge headroom


def cache_path(data_dir):
    return os.path.join(data_dir, CACHE_NAME)


def load_cache(data_dir):
    try:
        with open(cache_path(data_dir), encoding="utf-8") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


def _atomic_write(path, obj):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _fresh_ts(entry, now):
    try:
        return (now - float(entry.get("ts") or 0)) <= POINT_TTL
    except Exception:
        return False


def fresh_entries(cache, route_id, now=None):
    """{date: entry} for one route, TTL-filtered, bad rows dropped."""
    now = now if now is not None else time.time()
    out = {}
    for d, e in ((cache.get(route_id) or {}).items()):
        if not isinstance(e, dict):
            continue
        try:
            _dt.date.fromisoformat(str(d))
            if float(e.get("bare")) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        if _fresh_ts(e, now):
            out[str(d)] = e
    return out
def put_rows(data_dir, route_id, rows, tax=0.0, now=None):
    """Persist captured rows. Each row: {date, total, flight_no?,
    dep_time?, arr_time?}; total is the pay price (tax included).
    Stored as bare (total - tax) to keep total_price() semantics.
    Returns (cache, n_stored); invalid rows are skipped, not fatal."""
    now = now if now is not None else time.time()
    cache = load_cache(data_dir)
    bucket = cache.setdefault(route_id, {}) if isinstance(cache, dict) else {}
    n = 0
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        d = str(r.get("date") or "").strip()
        try:
            _dt.date.fromisoformat(d)
            total = float(r.get("total"))
        except (TypeError, ValueError):
            continue
        if total <= 0:
            continue
        bucket[d] = {
            "bare": round(total - float(tax or 0), 1),
            "total": round(total, 1),
            "flight_no": str(r.get("flight_no") or "").strip(),
            "dep_time": str(r.get("dep_time") or "").strip()[:5],
            "arr_time": str(r.get("arr_time") or "").strip()[:5],
            "ts": now,
        }
        n += 1
    if len(bucket) > MAX_ROWS_PER_ROUTE:
        keep = sorted(bucket.items(), key=lambda kv: kv[1].get("ts", 0))
        cache[route_id] = dict(keep[-MAX_ROWS_PER_ROUTE:])
    _atomic_write(cache_path(data_dir), cache)
    return cache, n


def merge_point_fill(deals, cache, route_id, now=None):
    """Replace reference-only rows (interp/nearby-ref) with fresh
    point-fill rows. Real rows (qunar/amadeus/point) always win.
    Returns (deals, n_replaced); output sorted by (price, date)."""
    from .flights import NON_REAL_SOURCES
    from .models import FlightDeal
    entries = fresh_entries(cache, route_id, now)
    if not entries:
        return deals, 0
    out, replaced = [], 0
    for d in deals:
        e = entries.get(d.date)
        if e and getattr(d, "source", "") in NON_REAL_SOURCES:
            out.append(FlightDeal(
                date=d.date,
                bare_price=float(e["bare"]),
                flight_no=e.get("flight_no") or "",
                dep_time=e.get("dep_time") or "",
                arr_time=e.get("arr_time") or "",
                duration_text=d.duration_text,
                time_src=POINT_SOURCE,
                dep_src=POINT_SOURCE,
                arr_src=POINT_SOURCE,
                source=POINT_SOURCE,
                url=d.url,
            ))
            replaced += 1
        else:
            out.append(d)
    if replaced:
        out.sort(key=lambda x: (x.bare_price, x.date))
    return out, replaced


def patch_snapshot_deals(deals, cache, route_id, now=None):
    """Dict-row twin of merge_point_fill for the live snapshot: lets
    POST /api/point-fill reflect in the UI immediately, before the
    next crawl replays the same cache. Returns n_replaced."""
    entries = fresh_entries(cache, route_id, now)
    n = 0
    for d in deals or []:
        if not isinstance(d, dict):
            continue
        e = entries.get(str(d.get("date") or ""))
        if e and d.get("source") in ("interp", "nearby-ref"):
            d["bare_price"] = float(e["bare"])
            d["total_price"] = float(e.get("total") or e["bare"])
            d["source"] = POINT_SOURCE
            if e.get("flight_no"):
                d["flight_no"] = e["flight_no"]
            for k in ("dep_time", "arr_time"):
                if e.get(k):
                    d[k] = e[k]
            for k in ("time_src", "dep_src", "arr_src"):
                d[k] = POINT_SOURCE
            d["ref_offset"] = 0
            n += 1
    return n


def gap_dates(deals, window):
    """Dates still carrying reference-only prices -> capture targets.
    window is [date_from, date_to]; deals are raw snapshot dicts."""
    have_real = {str(d.get("date")) for d in deals or []
                 if d.get("source") not in ("interp", "nearby-ref")}
    out = []
    try:
        cur = _dt.date.fromisoformat(window[0])
        end = _dt.date.fromisoformat(window[1])
    except (TypeError, ValueError):
        return out
    while cur <= end:
        iso = cur.isoformat()
        if iso not in have_real:
            out.append(iso)
        cur += _dt.timedelta(days=1)
    return out
