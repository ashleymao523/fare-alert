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

v0.88: the SAME response carries flightOffers[] - full cheapest
itineraries with flight number, exact dep/arr timestamps, duration,
stop legs and the real checked-luggage allowance. Gap rows now ship
with exact times (dep_src=booking), and cached same-date itineraries
pin reference times onto real-price rows still missing exact
departures (dep_src=booking-x - the price row stays authoritative).

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
NEG_TTL_ERR = 90 * 60        # transient failure: retry fast
NEG_TTL_NODATA = 12 * 3600   # server-confirmed no offer
DEFAULT_FX = 7.8           # EUR -> CNY, config booking_fill.fx_eur_cny
DEFAULT_MAX_PER_CYCLE = 6
CALL_INTERVAL = 4.0
EXACT_SOURCES = ("amadeus", "airport-board", "booking")


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


def coverage_stats(data_dir):
    """v0.91: same-day timetable upgrade observability.

    Counts fresh positive cache entries (the reference quotes) and
    how many already carry a full Booking offers list. The gap is the
    legacy backlog the v0.90 rotation upgrades at max_per_cycle per
    route per round - surfaced in /api/health so deploy progress is
    visible without reading the cache by hand."""
    cache = _load(data_dir)
    now = time.time()
    pos = offers = 0
    for bucket in cache.values():
        if not isinstance(bucket, dict):
            continue
        for e in bucket.values():
            if not isinstance(e, dict):
                continue
            if float(e.get("cny") or 0) <= 0 or not _fresh(e, now, POS_TTL):
                continue
            pos += 1
            if e.get("offers"):
                offers += 1
    return {"pos": pos, "offers": offers,
            "pending": max(0, pos - offers),
            "pct": int(round(offers * 100.0 / pos)) if pos else 0}
def fetch_lowest(session, net_cfg, fi, ti, date):
    """One keyless LOWEST_PRICE call -> dict or None (no exception).

    Returns {"total_eur", "airline", "n_offers", ...itinerary};
    total_eur is the tax-inclusive grand total (matches amadeus fill
    semantics). v0.88 adds fno/dep/arr/dur/stop_kind/stop_city/stop_arr/
    craft/bag from flightOffers[0] when present.

    v0.88.1: a 200 answer with no aggregation.minPrice means the
    SERVER confirmed no offer -> {"no_data": True} (long negative
    cache). Non-200 / transport errors return None - those are
    transient (throttle, hiccup) and live probing proves the date
    often prices minutes later, so they only get a short negative
    cache. This split is what kills the grey-date complaint: dates
    a manual precise search CAN find were previously locked out for
    24h by one unlucky call."""
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
        return {"no_data": True}
    nanos = float(mp.get("nanos") or 0) / 1e9
    total = float(units) + (nanos if nanos < 1 else 0.0)
    airline = ""
    for s in agg.get("stops") or []:
        code = ((s.get("cheapestAirline") or {}).get("code") or "")
        if code:
            airline = code
            break
    got = {"total_eur": round(total, 1), "airline": airline,
           "n_offers": int(agg.get("totalCount") or 0)}
    got.update(offer_itinerary(j))
    got["offers"] = offer_list(j)
    return got


_CRAFT_NAMES = {
    "738": "波音737-800", "73H": "波音737-800", "739": "波音737-900",
    "32N": "空客A320neo", "A20N": "空客A320neo", "A21N": "空客A321neo",
    "320": "空客A320", "321": "空客A321", "323": "空客A321",
    "333": "空客A330-300", "339": "空客A330-900", "359": "空客A350-900",
    "77W": "波音777-300ER", "789": "波音787-9", "788": "波音787-8",
    "919": "中国商飞C919",
}


def _hhmm(iso):
    s = str(iso or "")
    return s[11:16] if len(s) >= 16 else ""


def _dur_text(dep_iso, arr_iso):
    try:
        d0 = _dt.datetime.fromisoformat(str(dep_iso)[:19])
        d1 = _dt.datetime.fromisoformat(str(arr_iso)[:19])
        mins = int((d1 - d0).total_seconds() // 60)
    except Exception:
        return ""
    if mins < 0:
        mins += 24 * 60
    return "%dh%02dm" % (mins // 60, mins % 60)


def _bag_text(segs):
    for s in segs:
        for t in (s.get("travellerCheckedLuggage") or []):
            la = t.get("luggageAllowance") or {}
            if la.get("luggageType") != "CHECKED_IN":
                continue
            w = la.get("maxTotalWeight")
            pc = la.get("maxPiece")
            if w:
                return "含%skg托运" % w
            if pc:
                return "含%spc托运" % pc
    return "无免费托运"


def offer_itinerary(j):
    """flightOffers[0] -> exact itinerary fields ({} when absent)."""
    offers = j.get("flightOffers") or []
    if not offers:
        return {}
    segs = offers[0].get("segments") or []
    if not segs:
        return {}
    first, last = segs[0], segs[-1]
    legs = first.get("legs") or []
    leg0 = legs[0] if legs else {}
    info = leg0.get("flightInfo") or {}
    mk = ((info.get("carrierInfo") or {}).get("marketingCarrier") or "")
    num = info.get("flightNumber") or ""
    dep_iso = first.get("departureTime") or ""
    arr_iso = last.get("arrivalTime") or ""
    out = {
        "fno": ("%s%s" % (mk, num)) if (mk and num) else "",
        "dep": _hhmm(dep_iso), "arr": _hhmm(arr_iso),
        "dur": _dur_text(dep_iso, arr_iso),
        "stop_kind": "", "stop_city": "", "stop_arr": "",
        "craft": _CRAFT_NAMES.get(str(info.get("planeType") or "").upper(),
                                  str(info.get("planeType") or "")),
        "bag": _bag_text(segs),
    }
    if len(segs) > 1:
        ap = segs[0].get("arrivalAirport") or {}
        out.update(stop_kind="transfer", stop_city=ap.get("code") or "",
                   stop_arr=_hhmm(segs[0].get("arrivalTime") or ""))
    elif len(legs) > 1:
        ap = (legs[-1].get("departureAirport") or {})
        out.update(stop_kind="via", stop_city=ap.get("code") or "",
                   stop_arr=_hhmm(first.get("arrivalTime") or ""))
    return out


def offer_list(j, limit=8):
    """v0.89: every flightOffers itinerary -> same-day timetable rows.

    The LOWEST_PRICE response carries ~15 complete offers (different
    flights, each with exact timestamps). Parsing only offers[0] (the
    cheapest) answers "when does THE cheapest fly" but the user's
    standing complaint is "I cannot see the departure times of the
    flights on this date" - so keep them all (deduped by flight no,
    sorted by departure) for the snapshot alt_times and the
    day-schedule strip."""
    rows, seen = [], set()
    for of in (j.get("flightOffers") or [])[:limit * 2]:
        segs = of.get("segments") or []
        if not segs:
            continue
        first, last = segs[0], segs[-1]
        legs = first.get("legs") or []
        leg0 = legs[0] if legs else {}
        info = leg0.get("flightInfo") or {}
        mk = ((info.get("carrierInfo") or {}).get(
            "marketingCarrier") or "")
        num = info.get("flightNumber") or ""
        fno = ("%s%s" % (mk, num)) if (mk and num) else ""
        dep = _hhmm(first.get("departureTime") or "")
        if not (fno and dep) or fno in seen:
            continue
        seen.add(fno)
        stop_city = ""
        if len(segs) > 1:
            stop_city = (segs[0].get("arrivalAirport")
                         or {}).get("code") or ""
        elif len(legs) > 1:
            stop_city = ((legs[-1].get("departureAirport")
                          or {}).get("code") or "")
        try:
            from .flights import airline_name
            al = airline_name(fno[:2]) if len(fno) >= 2 else ""
        except Exception:
            al = ""
        rows.append({
            "no": fno, "dep": dep,
            "arr": _hhmm(last.get("arrivalTime") or ""),
            "dur": _dur_text(first.get("departureTime") or "",
                             last.get("arrivalTime") or ""),
            "airline": al or mk,
            "craft": _CRAFT_NAMES.get(
                str(info.get("planeType") or "").upper(),
                str(info.get("planeType") or "")),
            "via": stop_city,
        })
        if len(rows) >= limit:
            break
    rows.sort(key=lambda r: (r["dep"], r["no"]))
    return rows


def _fresh(entry, now, ttl):
    try:
        return (now - float(entry.get("ts") or 0)) <= ttl
    except Exception:
        return False


def fill_gaps(session, net_cfg, cfg, fi, ti, gap_dates, tax, data_dir,
              route_id, stats=None, sleeper=None, extra_dates=None):
    """Return list[FlightDeal] (source=booking-ref) for gap dates.

    Near-date-first rotation: fresh positive cache rows replay free;
    uncached dates are probed live up to max_per_cycle per round; the
    negative cache doubles as the rotation cursor (same pattern as the
    v0.67 amadeus offer budget). Errors never raise - the caller's
    pipeline must stay alive.

    v0.88: extra_dates are real-price dates whose cheapest row still
    lacks an exact departure; probing them sedimentates the same cache
    (attach_times consumes it later) - they never produce rows here,
    the qunar price stays authoritative. v0.87 cache entries without
    itinerary fields are re-probed once so rows upgrade to exact times
    organically.

    v0.90: fresh positive entries WITHOUT an offers list are legacy
    (pre-v0.89 single-itinerary quotes). They now re-enter the probe
    rotation so every cached date upgrades to the full same-day
    timetable; a failed upgrade probe KEEPS the legacy quote (it only
    loses the timetable, never the reference price) and retries next
    round - the cache cursor therefore never stalls again.

    v0.93: two anti-starvation fixes, both born from the live grey-
    date deadlock the user re-reported ("dates the calendar leaves
    grey still answer a direct point query"). A pre-v0.88 zombie
    worker had written legacy 4-key entries (cny only, no dep/no
    offers); the v0.88 replay gate then demanded dep+offers so those
    rows NEVER replayed, and the v0.90 upgrade rotation never reached
    them because targets sorted gap dates together with time-gaps -
    the 6-per-cycle budget was always eaten by nearer extra dates.
    Fix A: gap dates now outrank extra dates in the probe queue (and
    within each group nearer dates first) - a visible grey date can
    never be starved by schedule upgrades. Fix B: a fresh positive
    entry replays its reference price even without itinerary fields
    (v0.87 honesty: a real GDS quote beats a synthetic interp row);
    the times simply ride the upgrade rotation afterwards."""
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

    gap_set = {str(d) for d in (gap_dates or [])}
    # v0.93 fix A: gap dates (visible grey dots) outrank extra dates
    # (schedule upgrades); near-first inside each group. The old flat
    # sorted() let a flood of near time-gaps eat the whole 6-per-cycle
    # budget and starve far grey dates forever.
    targets = (sorted(gap_set) +
               sorted(str(d) for d in (extra_dates or [])
                      if str(d) not in gap_set))
    cache = _load(data_dir)
    bucket = cache.setdefault(route_id, {}) if isinstance(cache, dict) else {}
    now = time.time()
    out, probed, deferred, last_call = [], 0, 0, 0.0
    for d in targets:
        try:
            _dt.date.fromisoformat(str(d))
        except ValueError:
            continue
        e = bucket.get(d)
        full = bool(e and e.get("dep") is not None
                    and (e.get("offers") or []))
        # v0.87 zombie-worker entries carry cny but NO itinerary keys
        # at all (missing dep key); entries WITH dep but no offers are
        # v0.89 legacy quotes that keep riding the v0.90 upgrade
        # rotation instead - only the truly bare ones replay cold.
        zombie = bool(e and "dep" not in e)
        if (e and _fresh(e, now, POS_TTL)
                and float(e.get("cny") or 0) > 0
                and (full or (zombie and d in gap_set))):
            # v0.93 fix B: zombie entries (price, zero itinerary)
            # replay on gap dates - the reference price fills the
            # grey dot now; times ride the next expired re-probe.
            if d in gap_set:
                out.append(_deal_from(e, d, tax))
            continue
        if e and float(e.get("cny") or 0) <= 0:
            ttl = NEG_TTL_NODATA if e.get("kind") == "nodata" \
                else NEG_TTL_ERR
            if _fresh(e, now, ttl):
                deferred += 1      # fresh negative: skip this round
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
                         "n": got.get("n_offers") or 0,
                         "fno": got.get("fno") or "",
                         "dep": got.get("dep") or "",
                         "arr": got.get("arr") or "",
                         "dur": got.get("dur") or "",
                         "stop_kind": got.get("stop_kind") or "",
                         "stop_city": got.get("stop_city") or "",
                         "stop_arr": got.get("stop_arr") or "",
                         "craft": got.get("craft") or "",
                         "bag": got.get("bag") or "",
                         "offers": got.get("offers") or []}
            if d in gap_set:
                out.append(_deal_from(bucket[d], d, tax))
        else:
            if e and float(e.get("cny") or 0) > 0:
                # legacy positive quote: a failed timetable upgrade
                # must not destroy the cached reference price
                # v0.93: refresh ts so the surviving quote gets a
                # 48h cooldown (no per-round retry storm), and a gap
                # date still replays the old price this round - a
                # stale GDS reference beats a synthetic interp row.
                e["ts"] = now
                if d in gap_set:
                    out.append(_deal_from(e, d, tax))
                deferred += 1
                continue
            bucket[d] = {"ts": now, "cny": 0,
                         "kind": "nodata" if (got and got.get("no_data"))
                         else "err"}
    if probed:
        _save(data_dir, cache)
    stats.update({"probed": probed, "deferred": deferred, "filled": len(out)})
    return out


def _deal_from(entry, d, tax):
    """Cache entry -> full FlightDeal (source=booking-ref, exact times
    whenever the offer carried them)."""
    from .models import FlightDeal

    cny = float(entry.get("cny") or 0)
    dep = entry.get("dep") or ""
    arr = entry.get("arr") or ""
    fno = entry.get("fno") or entry.get("airline") or ""
    deal = FlightDeal(
        date=d, bare_price=round(cny - tax, 1),
        flight_no=fno, source=BOOKING_REF, url="", ref_offset=-1,
        dep_time=dep, arr_time=arr, duration_text=entry.get("dur") or "",
        time_src="booking" if dep else "",
        dep_src="booking" if dep else "",
        arr_src="booking" if arr else "",
        stop_kind=entry.get("stop_kind") or "",
        stop_city=entry.get("stop_city") or "",
        stop_arr=entry.get("stop_arr") or "",
        baggage_note=entry.get("bag") or "")
    offers = entry.get("offers") or []
    if offers:
        deal.alt_times = [{"no": o.get("no"), "dep": o.get("dep"),
                           "arr": o.get("arr"), "airline": o.get("airline"),
                           "craft": o.get("craft"), "via": o.get("via"),
                           "dur": o.get("dur") or "",
                           "exact": True, "src": "booking"}
                          for o in offers]
    elif dep:
        try:
            from .flights import airline_name
            al = airline_name(fno[:2]) if len(fno) >= 2 else ""
        except Exception:
            al = ""
        deal.alt_times = [{"no": fno, "dep": dep, "arr": arr,
                          "airline": al, "craft": entry.get("craft") or "",
                          "via": "", "exact": True}]
    return deal


def attach_times(deals, data_dir, route_id, stats=None):
    """v0.88: pin cached same-date Booking itineraries onto real-price
    rows whose dep time is missing or dow-borrowed (booking-x).

    Overwrite policy: exact sources (amadeus/airport-board) and alt-ref
    (same-flight reference) keep their times; only missing or
    airport-board-x (dow borrow) rows upgrade - a same-date real
    schedule beats a borrowed weekday. The price and flight identity
    of the real row are NEVER touched (the booking cheapest flight
    may differ from the OTA cheapest)."""
    from .flights import NON_REAL_SOURCES

    cache = _load(data_dir)
    bucket = cache.get(route_id) if isinstance(cache, dict) else None
    bucket = bucket or {}
    now = time.time()
    n = 0
    for d in deals:
        src = (getattr(d, "source", "") or "")
        if src in NON_REAL_SOURCES or getattr(d, "cabin", ""):
            continue
        dep_src = (getattr(d, "dep_src", "") or "") or \
            (getattr(d, "time_src", "") or "")
        if getattr(d, "dep_time", "") and \
                dep_src in EXACT_SOURCES + ("alt-ref",):
            continue
        e = bucket.get(getattr(d, "date", ""))
        if not e or not _fresh(e, now, POS_TTL):
            continue
        dep = e.get("dep") or ""
        if not dep or float(e.get("cny") or 0) <= 0:
            continue
        d.dep_time = dep
        d.dep_src = "booking-x"
        d.time_src = "booking-x"
        if not (getattr(d, "arr_time", "") or "").strip() and e.get("arr"):
            d.arr_time = e["arr"]
            d.arr_src = "booking-x"
        dur = e.get("dur") or ""
        if dur and (not getattr(d, "duration_text", "")
                   or "(估)" in (getattr(d, "duration_text", "") or "")):
            d.duration_text = dur
        # v0.90: a full same-day Booking timetable also replaces
        # unsourced board-reference alts (they never carry src); rows
        # that already show a booking timetable keep theirs.
        cur_alts = getattr(d, "alt_times", None) or []
        has_booking = any((a.get("src") or "") == "booking"
                          for a in cur_alts if isinstance(a, dict))
        offers = e.get("offers") or []
        if offers and not has_booking:
            d.alt_times = [{"no": o.get("no"), "dep": o.get("dep"),
                            "arr": o.get("arr"), "airline": o.get("airline"),
                            "craft": o.get("craft"), "via": o.get("via"),
                            "dur": o.get("dur") or "",
                            "exact": True, "src": "booking"}
                           for o in offers]
        n += 1
    if stats is not None:
        stats["attached"] = n
    return deals


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
