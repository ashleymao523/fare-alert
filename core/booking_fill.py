# -*- coding: utf-8 -*-
"""v0.87: keyless Booking.com cross-fill for grey calendar dates.

Recon (2026-09-15, live probes in data/_probe4-8.py): the qunar
priceCalendar gateway answers a row for EVERY date but leaves the
price field empty on ~320/365 rows - the server simply has no cached
floor price yet. The per-date qunar list API stays signature-gated
(v0.76 recon), but flights.booking.com/api/flights/LOWEST_PRICE is
keyless, browser-shaped and answers BOTH domestic and intl grey dates
with a real purchasable lowest quote (~3-5s per call).

The quote is a GDS international-channel price in EUR: real, but
usually HIGHER than the CN OTA price users will actually pay. Rows are
therefore tagged source=booking-ref and joined NON_REAL_SOURCES -
display + documentation only, never alerts/KPI/history. When the qunar
cache later prices the same date the real row wins on its own; a
point-fill capture may also overwrite it (merge conditions include
booking-ref since v0.87).

Budget: <= max_per_cycle fresh dates per crawl round (near-first
rotation like the amadeus offer fill), positive cache 48h, negative
24h, >=4s between live calls, quiet 429/5xx backoff.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import time

BOOKING_REF = "booking-ref"
ENDPOINT = "https://flights.booking.com/api/flights/LOWEST_PRICE"
CACHE_NAME = "booking_fill_cache.json"
POS_TTL = 48 * 3600
NEG_TTL = 24 * 3600
DEFAULT_FX = 7.8           # EUR -> CNY, config booking_fill.fx_eur_cny
DEFAULT_MAX_PER_CYCLE = 6
CALL_INTERVAL = 4.0


def cache_path(data_dir):
    return os.path.join(data_dir, CACHE_NAME)


def _load(data_dir):
    try:
        with open(cache_path(data_dir), encoding="utf-8") as f:
            c = json.load(f)
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}


def _save(data_dir, cache):
    path = cache_path(data_dir)
    tmp = path + ".%d.tmp" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def fetch_lowest(session, net_cfg, fi, ti, date):
    """One keyless LOWEST_PRICE call -> dict or None (no exception).

    Returns {"total_eur", "airline", "n_offers"}; total_eur is the
    tax-inclusive grand total (matches amadeus fill semantics)."""
    params = {
        "type": "ONEWAY", "from": fi, "to": ti, "depart": date,
        "adults": "1", "cabinClass": "ECONOMY",
        "market": "zh-CN", "locale": "zh-CN",
    }
    headers = {
        "User-Agent": net_cfg.get(
            "user_agent_desktop",
            net_cfg.get("user_agent",
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")),
        "Accept": "application/json",
        "Referer": "https://flights.booking.com/",
    }
    r = session.get(ENDPOINT, params=params, headers=headers,
                    timeout=net_cfg.get("timeout_seconds", 25))
    if r.status_code != 200:
        return None
    j = r.json()
    agg = j.get("aggregation") or {}
    mp = agg.get("minPrice") or {}
    units = mp.get("units")
    if units is None:
        return None
    nanos = float(mp.get("nanos") or 0) / 1e9
    total = float(units) + (nanos if nanos < 1 else 0.0)
    airline = ""
    for s in agg.get("stops") or []:
        code = ((s.get("cheapestAirline") or {}).get("code") or "")
        if code:
            airline = code
            break
    return {"total_eur": round(total, 1), "airline": airline,
            "n_offers": int(agg.get("totalCount") or 0)}


def _fresh(entry, now, ttl):
    try:
        return (now - float(entry.get("ts") or 0)) <= ttl
    except Exception:
        return False


def fill_gaps(session, net_cfg, cfg, fi, ti, gap_dates, tax, data_dir,
              route_id, stats=None, sleeper=None):
    """Return list[FlightDeal] (source=booking-ref) for gap dates.

    Near-date-first rotation: fresh positive cache rows replay free;
    uncached dates are probed live up to max_per_cycle per round; the
    negative cache doubles as the rotation cursor (same pattern as the
    v0.67 amadeus offer budget). Errors never raise - the caller's
    pipeline must stay alive."""
    from .alerts import tax_amount
    from .models import FlightDeal

    stats = stats if stats is not None else {}
    bk_cfg = (cfg.get("booking_fill") or {}) if isinstance(cfg, dict) else {}
    fx = float(bk_cfg.get("fx_eur_cny", DEFAULT_FX) or DEFAULT_FX)
    max_n = int(bk_cfg.get("max_per_cycle", DEFAULT_MAX_PER_CYCLE)
                or DEFAULT_MAX_PER_CYCLE)
    interval = float(bk_cfg.get("call_interval", CALL_INTERVAL) or CALL_INTERVAL)
    tax = tax if tax is not None else tax_amount(cfg.get("tax", {}))
    sleeper = sleeper or time.sleep

    cache = _load(data_dir)
    bucket = cache.setdefault(route_id, {}) if isinstance(cache, dict) else {}
    now = time.time()
    out, probed, deferred, last_call = [], 0, 0, 0.0
    for d in sorted(gap_dates or []):
        try:
            _dt.date.fromisoformat(str(d))
        except ValueError:
            continue
        e = bucket.get(d)
        if e and _fresh(e, now, POS_TTL) and float(e.get("cny") or 0) > 0:
            out.append(FlightDeal(
                date=d, bare_price=round(float(e["cny"]) - tax, 1),
                flight_no=e.get("airline") or "", source=BOOKING_REF,
                url="", ref_offset=-1))
            continue
        if e and _fresh(e, now, NEG_TTL) and float(e.get("cny") or 0) <= 0:
            deferred += 1          # known-empty recently: skip this round
            continue
        if probed >= max_n:
            deferred += 1
            continue
        if last_call:
            sleeper(interval)
        last_call = time.time()
        probed += 1
        try:
            got = fetch_lowest(session, net_cfg, fi, ti, d)
        except Exception:
            got = None
        if got and got.get("total_eur", 0) > 0:
            cny = round(got["total_eur"] * fx, 0)
            bucket[d] = {"ts": now, "cny": cny,
                         "airline": got.get("airline") or "",
                         "n": got.get("n_offers") or 0}
            out.append(FlightDeal(
                date=d, bare_price=round(cny - tax, 1),
                flight_no=got.get("airline") or "", source=BOOKING_REF,
                url="", ref_offset=-1))
        else:
            bucket[d] = {"ts": now, "cny": 0}
    if probed:
        _save(data_dir, cache)
    stats.update({"probed": probed, "deferred": deferred, "filled": len(out)})
    return out


def merge_booking_deals(deals, bk_deals, booking_url_fn):
    """Only dates still missing get a booking-ref row; the purchase
    url keeps pointing at the OTA deep link (the quote itself is a
    reference, the click should land where users actually buy).
    Returns (merged_sorted, n_added)."""
    have = {d.date for d in deals}
    added = []
    for d in bk_deals:
        if d.date in have:
            continue
        d.url = booking_url_fn(d.date)
        added.append(d)
    merged = list(deals) + added
    merged.sort(key=lambda x: (x.bare_price, x.date))
    return merged, len(added)
