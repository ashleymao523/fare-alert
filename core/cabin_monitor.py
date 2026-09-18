# -*- coding: utf-8 -*-
"""v0.42: business-cabin low-fare collector + alert."""
from __future__ import annotations

import json
import os
from datetime import date as _date, datetime, timedelta

from .booking_fill import DEFAULT_FX
from .models import FlightDeal

HISTORY_CAP = 300

# v1.30: precision classes per observation source. A qunar
# pay-total captured on the real OTA page is ground truth; an
# Amadeus offer is real inventory priced in EUR conversion; a
# keyless booking aggregate is an estimate (full-fare biased).
# Open-source recon (qunar-flight-reminder, SpiderApplication et
# al.) shows no maintained signature bypass, so the real-browser
# capture stays the precise source and history entries must carry
# WHICH class they are.
SRC_CLASS = {"qunar": 2, "point-cabin": 2, "amadeus": 1, "booking": 0}


def src_class(src):
    """Precision class of an observation source string (0=estimate
    when unknown/legacy). Pure."""
    return SRC_CLASS.get(str(src or "").strip().lower(), 0)


def default_config():
    return {
        "enabled": False,
        "cabins": ["business"],
        "default_to_city": "杭州",
        "to_cities": ["杭州"],
        "threshold_total": 1500.0,
        "cooldown_hours": 12.0,
        # v0.66: standalone patrol cadence - the cabin watch refreshes
        # on its own clock, not only when a full route scan happens.
        "refresh_minutes": 30,
        # v1.09: keyless BUSINESS probes per leg per patrol round -
        # the whole 60d window rotates over successive rounds.
        "probe_dates_per_round": 12,
        "watch_from_cities": [],
        # v0.52: a fresh all-time low alerts even ABOVE the threshold -
        # "collect + remind on historical lowest business fares" needs
        # the record event itself, not only a fixed price line.
        "alert_record_low": True,
        # v1.25: optional per-leg thresholds keyed "出发>目的" (total
        # CNY). Beijing->Shanghai reality (low ~1277) and Chongqing->
        # Shanghai (~1468) sit ABOVE the global 1000 default, so a
        # single global line never fires for them; a leg may now set
        # its own realistic line while others keep the global one.
        "route_thresholds": {},
    }


def load_config(cfg):
    base = default_config()
    user = (cfg or {}).get("cabin_watch") or {}
    base.update({k: v for k, v in user.items() if v is not None})
    if "to_cities" not in user:
        # no explicit list in the user config: drop the default's so the
        # legacy single-field destination re-derives it below
        base["to_cities"] = []
    # v0.47: destinations are a list (default Hangzhou, freely editable).
    # Legacy single-value configs derive their list from default_to_city;
    # default_to_city stays synced to the first entry for old readers.
    tos = [str(c).strip() for c in (base.get("to_cities") or [])
           if str(c).strip()]
    if not tos:
        legacy = (base.get("default_to_city") or "").strip()
        tos = [legacy] if legacy else ["杭州"]
    dedup = []
    for c in tos:
        if c not in dedup:
            dedup.append(c)
    base["to_cities"] = dedup
    base["default_to_city"] = dedup[0]
    return base


def _atomic_write(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, path)


def load_history(data_dir):
    path = os.path.join(data_dir, "cabin_history.json")
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict):
            if _migrate_v130(obj):
                try:
                    _atomic_write(path, obj)
                except OSError:
                    pass  # read-only media: re-derive next load
            return obj
    except (OSError, ValueError):
        pass
    return {"routes": {}}


def _obs_better(o, cur):
    """True when observation o should replace cur for the same
    (date, cabin, fno) slot: higher precision class wins outright;
    within a class the newer ts wins (legacy replace semantics)."""
    oc, cc = src_class(o.get("src")), src_class(cur.get("src"))
    if oc != cc:
        return oc > cc
    return str(o.get("ts") or "") >= str(cur.get("ts") or "")


def _migrate_v130(obj):
    """v1.30 one-shot: merge legacy point-*/patrol-* route ids into
    one canonical leg-* route per real-world city pair.

    The v0.42-v1.29 layout kept TWO history routes for the same leg
    (booking patrol wrote patrol-*, qunar captures wrote point-*), so
    the leaderboard showed duplicates with wildly different lows and
    the threshold check ran per duplicate - a full-fare booking
    estimate of 4487 sat next to the real qunar 1200 for the same
    flight. Migration stamps each merged row with its origin source
    (point-* -> qunar, patrol-* -> booking) and dedups per
    (date, cabin, fno) precise-wins. Idempotent; returns True when
    the object changed (caller persists)."""
    routes = obj.get("routes") or {}
    if not any(str(k).startswith(("point-", "patrol-"))
               for k in routes):
        return False
    out = {}
    for rid, r in routes.items():
        rid = str(rid)
        if rid.startswith("point-"):
            new_id, src = "leg-" + rid[6:], "qunar"
        elif rid.startswith("patrol-"):
            new_id, src = "leg-" + rid[7:], "booking"
        else:
            out[rid] = r
            continue
        cur = out.setdefault(new_id, {
            "from_city": (r.get("from_city") or ""),
            "to_city": (r.get("to_city") or ""),
            "obs": [], "lowest": None})
        if not cur.get("from_city"):
            cur["from_city"] = r.get("from_city") or ""
        if not cur.get("to_city"):
            cur["to_city"] = r.get("to_city") or ""
        for o in (r.get("obs") or []):
            if isinstance(o, dict) and not (o.get("src") or "").strip():
                o["src"] = src
            cur.setdefault("obs", []).append(o)
    for rid, r in out.items():
        best = {}
        for o in (r.get("obs") or []):
            if not isinstance(o, dict):
                continue
            key = (o.get("date") or "", o.get("cabin") or "",
                   (o.get("fno") or ""))
            if key not in best or _obs_better(o, best[key]):
                best[key] = o
        obs = sorted(best.values(),
                     key=lambda o: o.get("date") or "")
        if len(obs) > HISTORY_CAP:
            del obs[:len(obs) - HISTORY_CAP]
        lows = [o["price"] for o in obs
                if isinstance(o.get("price"), (int, float))]
        r["obs"] = obs
        r["lowest"] = min(lows) if lows else None
    obj["routes"] = out
    return True


def absorb_point_cabin(cache, cw, now=None):
    """v0.83: pull cabin-tagged rows out of the point-fill cache.

    The business watch stays alive WITHOUT any Amadeus key: rows a
    real browser captured on a cabin-filtered qunar page (bookmarklet
    generated with ?cabin=) carry a cabin tag here and feed the same
    ring history + record-low alerts the Amadeus patrol writes. TTL
    mirrors the point cache (stale captures must not refresh history).
    Returns leg-grouped {hid: {"leg": {from_city, to_city},
    "rows": [{date, total, flight_no, dep_time, arr_time, cabin}]}}
    - pure, no IO."""
    import time as _time
    now = now if now is not None else _time.time()
    ttl = 48 * 3600
    cabins = {str(c).strip().lower()
              for c in (cw.get("cabins") or ["business"])}
    out = {}
    for _route_id, bucket in (cache or {}).items():
        if not isinstance(bucket, dict):
            continue
        for date, e in bucket.items():
            if not isinstance(e, dict):
                continue
            try:
                if now - float(e.get("ts") or 0) > ttl:
                    continue
            except (TypeError, ValueError):
                continue
            cab = str(e.get("cabin") or "").strip().lower()
            if cab not in cabins:
                continue
            try:
                total = float(e.get("total"))
                if total <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            fc = str(e.get("from_city") or "").strip()
            tc = str(e.get("to_city") or "").strip()
            if not (fc and tc):
                continue
            hid = "leg-%s-%s" % (fc, tc)
            g = out.setdefault(hid, {
                "leg": {"from_city": fc, "to_city": tc}, "rows": []})
            g["rows"].append({
                "date": str(date), "total": round(total, 1),
                "flight_no": str(e.get("flight_no") or ""),
                "dep_time": str(e.get("dep_time") or ""),
                "arr_time": str(e.get("arr_time") or ""),
                "cabin": cab,
            })
    return out


def record_low(history, route_id, from_city, to_city, cabin, date,
               price_total, fno="", dep="", arr="", source=""):
    """Insert one business-cabin observation; ring-cap per route.
    v1.10 precision: the dedup key is (date, cabin, FLIGHT) - the
    booking timetable feeds several business flights per date now,
    so different flights coexist while a same-flight re-observation
    replaces (latest wins). Legacy fno-less callers share the ""
    slot, which reproduces the old same-date semantics exactly.
    Returns the inserted observation, tagged record=True when it
    undercuts the leg's previous all-time low (first sample is never
    a record - otherwise bootstrap would alert on everything)."""
    routes = history.setdefault("routes", {})
    r = routes.setdefault(route_id, {
        "from_city": from_city, "to_city": to_city,
        "obs": [], "lowest": None,
    })
    r["from_city"] = from_city or r.get("from_city", "")
    r["to_city"] = to_city or r.get("to_city", "")
    obs = r.setdefault("obs", [])
    lows = [o["price"] for o in obs
            if isinstance(o.get("price"), (int, float))]
    prior = min(lows) if lows else None
    fno = str(fno or "")
    dup = None
    for o in obs:
        if (o.get("date") == date and o.get("cabin") == cabin
                and (o.get("fno") or "") == fno):
            dup = o
            break
    if dup is not None and src_class(source) < src_class(dup.get("src")):
        # v1.30 precision contract: an estimate never overwrites a
        # precise row of the same flight - return the incumbent so
        # callers treat it as a no-record observation. Strip the
        # incumbent's stale record tag: the dup dict IS the stored
        # entry and keeps its historical flag, but returning it raw
        # would let _cabin_absorb re-arm a phantom new-record push.
        return {k: v for k, v in dup.items()
                if k not in ("record", "record_prev")}
    if dup is not None:
        obs.remove(dup)
    entry = {"date": date, "cabin": cabin, "price": price_total,
             "fno": fno,
             "dep": str(dep or ""), "arr": str(arr or ""),
             "src": str(source or ""),
             "ts": datetime.now().strftime("%Y-%m-%dT%H:%M")}
    if (prior is not None and isinstance(price_total, (int, float))
            and price_total < prior):
        entry["record"] = True       # fresh all-time low for this leg
        entry["record_prev"] = prior
    obs.append(entry)
    obs.sort(key=lambda o: o.get("date") or "")
    if len(obs) > HISTORY_CAP:
        del obs[:len(obs) - HISTORY_CAP]
    lows = [o["price"] for o in obs
            if isinstance(o.get("price"), (int, float))]
    r["lowest"] = min(lows) if lows else None
    return entry


def _newest_timed(route):
    """v1.14: per date -> (newest obs ts, timed flag).

    timed = the newest-obs batch for that date carries at least one
    dep+arr pair (rows captured by the same probe share one ts)."""
    latest = {}
    for o in route.get("obs") or []:
        d = str(o.get("date") or "")
        if not d:
            continue
        ts = str(o.get("ts") or "")
        timed = bool((o.get("dep") or "") and (o.get("arr") or ""))
        if d not in latest or ts > latest[d][0]:
            latest[d] = (ts, timed)
        elif ts == latest[d][0] and timed:
            latest[d] = (ts, True)
    return latest


def _gap_map(route):
    """v1.14: per date -> deserves a precise re-probe?

    Two gap kinds, both leaving the UI unable to show a departure
    time: (a) the newest obs batch carries NO dep/arr at all (an
    anonymous minPrice floor row); (b) the date's CHEAPEST
    fno-carrying row is timeless - a legacy point-fill row that
    outranks every newer timed obs of the same flight by price
    forever unless re-probed and upgraded."""
    latest = _newest_timed(route)
    cheap = {}
    for o in route.get("obs") or []:
        d = str(o.get("date") or "")
        if not d or not (o.get("fno") or ""):
            continue
        p = o.get("price")
        if not isinstance(p, (int, float)):
            continue
        if d not in cheap or p < cheap[d]["price"]:
            cheap[d] = o
    gaps = {}
    for d, (ts, timed) in latest.items():
        if not timed:
            gaps[d] = True
    for d, o in cheap.items():
        if not ((o.get("dep") or "") and (o.get("arr") or "")):
            gaps[d] = True
    # v1.30: precision gap (c) - a date whose only src-tagged
    # observations are estimates (booking aggregate / EUR-derived)
    # lacks qunar pay-total ground truth even when its times are
    # complete, so it deserves a real-browser capture exactly like a
    # timeless one. Legacy src-less rows are NOT flagged: they keep
    # the pure v1.14 time-gap contract (and old test fixtures stay
    # meaningful).
    est_dates, precise_dates = set(), set()
    for o in route.get("obs") or []:
        d = str(o.get("date") or "")
        s = str(o.get("src") or "").strip().lower()
        if not (d and s):
            continue
        if src_class(s) >= 2:
            precise_dates.add(d)
        else:
            est_dates.add(d)
    for d in est_dates - precise_dates:
        gaps[d] = True
    return gaps


def probe_dates(history, route_id, date_from, date_to, k=6,
                time_first=True):
    """v1.09: which dates deserve the next keyless BUSINESS probe.

    Every date in the window sorts by its last observation ts -
    never-probed ('') first, then stalest; ties break on the earlier
    date. Taking the head rotates the whole window over successive
    rounds with zero extra state: a restart simply resumes from
    whatever the history ring says. Pure function.

    v1.14: time-gap-first. A date whose newest observation batch has
    NO dep/arr (an anonymous minPrice floor row) looks "fresh" by ts
    yet can never render a departure time - it now jumps the queue
    right after never-probed dates, so precise re-probes refill the
    empty time cells first instead of waiting for the full window
    rotation. time_first=False keeps the pure v1.09 ordering."""
    try:
        d0 = datetime.strptime(str(date_from), "%Y-%m-%d").date()
        d1 = datetime.strptime(str(date_to), "%Y-%m-%d").date()
    except Exception:
        return []
    if k <= 0 or d1 < d0:
        return []
    days = []
    cur = d0
    while cur <= d1 and len(days) < 400:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    route = ((history or {}).get("routes") or {}).get(route_id) or {}
    latest = _newest_timed(route)
    gaps = _gap_map(route) if time_first else {}

    def _key(d):
        if d not in latest:
            pri = 0
        elif d in gaps:
            pri = 1
        else:
            pri = 2
        return (pri, latest.get(d, ("",))[0], d)

    days.sort(key=_key)
    if not (time_first and gaps):
        return days[:k]
    # v1.14: budget split. A fresh 60d window starts with dozens of
    # never-probed dates that would hog the whole k budget, starving
    # the gap repair for days. Up to half the slots go to gaps first
    # (repair what the UI shows), the rest keeps the rotation moving.
    gap_days = [d for d in days if d in gaps]
    norm_days = [d for d in days if d not in gaps]
    n_gap = min(len(gap_days), max(1, k // 2))
    out = gap_days[:n_gap]
    out.extend(d for d in norm_days if len(out) < k)
    return out[:k]


def time_gap_dates(history, route_id, date_from, date_to):
    """v1.14: window dates whose newest observation batch lacks
    dep/arr - the exact precise-re-probe targets. Pure."""
    try:
        d0 = datetime.strptime(str(date_from), "%Y-%m-%d").date()
        d1 = datetime.strptime(str(date_to), "%Y-%m-%d").date()
    except Exception:
        return []
    if d1 < d0:
        return []
    route = ((history or {}).get("routes") or {}).get(route_id) or {}
    gaps = _gap_map(route)
    out = []
    cur = d0
    while cur <= d1:
        iso = cur.isoformat()
        if iso in gaps:
            out.append(iso)
        cur += timedelta(days=1)
    return out


def patrol_gap(base_seconds, prev_streak, throttle_hits):
    """v1.15.1: adaptive 429 backoff for the patrol clock.

    A round with ANY throttle hit escalates the consecutive-broken
    streak: 2x base the first time, 4x the second, 6x capped after;
    a clean round (zero hits) resets to base. Pure - the worker loop
    and the manual trigger share it through state['_cabin_patrol'].
    Returns (effective_gap_seconds, streak)."""
    thr = int(throttle_hits or 0)
    streak = (int(prev_streak or 0) + 1) if thr else 0
    mult = min(2 ** streak, 6) if thr else 1
    return int(base_seconds) * mult, streak

def booking_cabin_rows(date, got, tax_amt, fx):
    """v1.10 precision: one booking LOWEST_PRICE BUSINESS answer ->
    [FlightDeal], one row PER BUSINESS FLIGHT.

    The answer carries a full same-day flightOffers timetable (~15
    offers, each with its OWN tax-inclusive EUR total and exact
    timestamps). v1.09 kept only aggregation.minPrice - one
    anonymous floor row per date; the history could say "this date
    has a business seat around X" but never WHICH flight, WHEN it
    departs or whether the cheap one is a red-eye. Now every offer
    becomes its own observation (fno/dep/arr preserved), minPrice
    stays as the no-offers fallback.

    bare = eur * fx - tax, so total_price() adds the tax back and
    reproduces the tax-inclusive pay-total exactly."""
    try:
        rate = float(fx or DEFAULT_FX)
    except (TypeError, ValueError):
        rate = DEFAULT_FX
    out = []
    for of in (got or {}).get("offers") or []:
        try:
            eur = float(of.get("price_eur") or 0)
        except (TypeError, ValueError):
            continue
        if eur <= 0 or not (of.get("no") and of.get("dep")):
            continue
        total = round(eur * rate, 1)
        out.append(FlightDeal(
            date=str(date),
            bare_price=round(total - float(tax_amt or 0), 1),
            flight_no=str(of.get("no") or ""),
            dep_time=str(of.get("dep") or ""),
            arr_time=str(of.get("arr") or ""),
            source="booking-cabin", cabin="business"))
    if out:
        return out
    try:
        eur = float((got or {}).get("total_eur") or 0)
    except (TypeError, ValueError):
        return []
    if eur <= 0:
        return []
    total = round(eur * rate, 1)
    return [FlightDeal(
        date=str(date),
        bare_price=round(total - float(tax_amt or 0), 1),
        flight_no=str((got or {}).get("fno") or ""),
        dep_time=str((got or {}).get("dep") or ""),
        arr_time=str((got or {}).get("arr") or ""),
        source="booking-cabin", cabin="business")]


def record_alert_candidate(new_records, alerted_low):
    """Best fresh record-low worth alerting, or None.

    new_records: this cycle's record-tagged observations (one leg).
    alerted_low: lowest price already alerted for the leg (None =
    never). A candidate must strictly undercut it, so each successive
    all-time low alerts exactly once and re-observing the same price
    never re-alerts. Pure."""
    if not new_records:
        return None
    best = min(new_records,
               key=lambda o: o.get("price")
               if isinstance(o.get("price"), (int, float)) else 1e18)
    p = best.get("price")
    if not isinstance(p, (int, float)):
        return None
    if alerted_low is not None and p >= float(alerted_low):
        return None
    return best


def route_qualifies(route, cw):
    """A route is watched when its to_city is the configured default
    destination (v0.47: any of the configured to_cities). from-city
    narrowing applies only when the operator filled watch_from_cities."""
    if not cw.get("enabled"):
        return False
    want = {str(c).strip() for c in (cw.get("to_cities") or [])
            if str(c).strip()}
    if not want:
        legacy = (cw.get("default_to_city") or "").strip()
        want = {legacy} if legacy else None
    if want is not None and (route.get("to_city") or "").strip() not in want:
        return False
    watch_from = cw.get("watch_from_cities") or []
    if watch_from:
        fc = (route.get("from_city") or "").strip()
        if fc not in watch_from:
            return False
    return True


def cabin_leg(route, cw):
    """v0.50: the business-watch leg a configured route feeds, if any.

    Direct: the route's to_city is watched -> collect the route itself.
    Mirror: the route's from_city is watched (and to_city is not) ->
    collect the reverse leg, so a HGH->CKG route also feeds the
    CKG->HGH business watch without manually adding reverse routes.
    watch_from_cities narrows by the WATCH leg's own departure city
    (mirror: the route's to_city). Returns None when the watch is off
    or neither end matches. Pure."""
    if not cw.get("enabled"):
        return None
    want = {str(c).strip() for c in (cw.get("to_cities") or [])
            if str(c).strip()}
    if not want:
        legacy = (cw.get("default_to_city") or "").strip()
        want = {legacy} if legacy else set()
    fc = (route.get("from_city") or "").strip()
    tc = (route.get("to_city") or "").strip()
    leg = None
    if tc and tc in want and fc:
        leg = {"mode": "direct", "from_city": fc, "to_city": tc}
    elif fc and fc in want and tc:
        leg = {"mode": "mirror", "from_city": tc, "to_city": fc}
    if leg is None:
        return None
    watch_from = {str(c).strip() for c in (cw.get("watch_from_cities") or [])
                  if str(c).strip()}
    if watch_from and leg["from_city"] not in watch_from:
        return None
    return leg


def patrol_legs(cw, routes=()):
    """v0.66: standalone watch legs - watch_from_cities x to_cities,
    minus pairs configured routes already feed (direct or mirror), so
    a departure city joins the business watch WITHOUT adding a reverse
    economy route. from==to drops; result sorted for stable display.
    Empty watch_from_cities keeps the legacy route-derived mode (no
    independent legs). Pure."""
    if not cw.get("enabled"):
        return []
    froms = []
    for c in (cw.get("watch_from_cities") or []):
        s = str(c).strip()
        if s and s not in froms:
            froms.append(s)
    tos = []
    for c in (cw.get("to_cities") or []):
        s = str(c).strip()
        if s and s not in tos:
            tos.append(s)
    if not froms or not tos:
        return []
    covered = set()
    for r in routes or []:
        leg = cabin_leg(r, cw)
        if leg:
            covered.add((leg["from_city"], leg["to_city"]))
    out = []
    for fc in froms:
        for tc in tos:
            if fc == tc or (fc, tc) in covered:
                continue
            out.append({"from_city": fc, "to_city": tc})
    return sorted(out, key=lambda x: (x["from_city"], x["to_city"]))


def evaluate_alert(history, cw, now=None):
    """Scan recorded business lows for threshold hits.
    Returns list of dicts for the notify layer (title/body/meta)."""
    if not cw.get("enabled"):
        return []
    hits = []
    for rid, r in (history.get("routes") or {}).items():
        obs = r.get("obs") or []
        if not obs:
            continue
        # v1.25: per-leg threshold first, global threshold as the
        # fallback - legs are priced independently in reality.
        threshold = leg_threshold(
            cw, r.get("from_city", ""), r.get("to_city", ""))
        if not threshold:
            continue
        best = min(obs, key=lambda o: o.get("price")
                   if isinstance(o.get("price"), (int, float)) else 1e18)
        price = best.get("price")
        if isinstance(price, (int, float)) and price <= threshold:
            hits.append({
                "route_id": rid,
                "from_city": r.get("from_city", ""),
                "to_city": r.get("to_city", ""),
                "date": best.get("date", ""),
                "cabin": best.get("cabin", "business"),
                "price": price,
                "threshold": threshold,
                # v1.17: carry the winning flight + times so the
                # notify layer can push "fno dep-arr" without a
                # history re-lookup.
                "fno": best.get("fno", ""),
                "dep": best.get("dep", ""),
                "arr": best.get("arr", ""),
            })
    return hits


def leg_threshold(cw, from_city, to_city):
    """v1.25: resolve the effective threshold for one leg.

    route_thresholds maps "出发>目的" -> total CNY and wins over the
    global threshold_total when it names this leg exactly. Keys accept
    Chinese city names or IATA codes (北京>上海 and BJS>SHA are the
    same leg; 上海 normalizes to SHA via core.intl). Entries with a
    non-positive or unparsable value are ignored. Falls back to the
    global threshold_total (0 = disabled). Pure."""
    def norm(city):
        c = str(city or "").strip()
        if not c:
            return ""
        from core.intl import city_iata
        return (city_iata(c) or c).strip().lower()
    fk, tk = norm(from_city), norm(to_city)
    if fk and tk:
        for k, v in (cw.get("route_thresholds") or {}).items():
            parts = [p.strip() for p in str(k).split(">") if p.strip()]
            if len(parts) != 2:
                continue
            try:
                tv = float(v)
            except (TypeError, ValueError):
                continue
            if tv <= 0:
                continue
            if norm(parts[0]) == fk and norm(parts[1]) == tk:
                return tv
    try:
        th = float(cw.get("threshold_total") or 0)
    except (TypeError, ValueError):
        return 0.0
    return th if th > 0 else 0.0


def borrow_sched_time(row, sched, from_city="", to_city=""):
    """v1.16: fill a timeless row's dep/arr from the zero-key schedule
    library (the same flights[fno][dow] store the economy board uses).

    Precision contract (the user asked for exact times, not guesses):
    borrow ONLY when flight no + departure weekday + both cities all
    match a schedule entry. Codeshares like 'CZ3502/CZ2326' try their
    first segment. A hit mutates the row in place (dep/arr/tsrc);
    returns True when the row was upgraded. Pure aside from the
    in-place row edit the caller owns."""
    if not sched or not isinstance(row, dict):
        return False
    if (row.get("dep") or "") and (row.get("arr") or ""):
        return False  # already timed - never overwrite real data
    fno = str(row.get("fno") or "").strip().upper()
    if "/" in fno:  # Booking codeshare string: first leg carries times
        fno = fno.split("/")[0].strip()
    if not fno:
        return False
    try:
        dow = str(_date.fromisoformat(
            str(row.get("date") or "")[:10]).weekday())
    except ValueError:
        return False
    ent = ((sched.get(fno) or {}).get("dows") or {}).get(dow)
    if not ent or not (ent.get("dep") and ent.get("arr")):
        return False
    sf, st = str(ent.get("from") or "").strip(), str(ent.get("to") or "").strip()
    cf, ct = str(from_city or "").strip(), str(to_city or "").strip()
    if sf and cf and sf != cf:
        return False  # same fno, different city pair - do not borrow
    if st and ct and st != ct:
        return False
    row["dep"] = str(ent.get("dep"))
    row["arr"] = str(ent.get("arr"))
    row["tsrc"] = "sched-borrow"
    return True


def push_time_suffix(row, sched=None, from_city="", to_city=""):
    """v1.17: '· HO1254 20:00–22:30' tail for a cabin push message.

    Uses the observation's own dep/arr first; a timeless row borrows
    from the schedule DB under borrow_sched_time's precision
    contract (in-place, never overwriting real times). Returns ''
    when no trustworthy pair exists, so the push stays clean."""
    if not isinstance(row, dict):
        return ""
    if not ((row.get("dep") or "") and (row.get("arr") or "")):
        if not borrow_sched_time(row, sched or {}, from_city, to_city):
            return ""

    def _hm(v):
        s = str(v or "").strip()
        if len(s) == 4 and ":" not in s:
            s = s[:2] + ":" + s[2:]
        return s[:5]

    dep, arr = _hm(row.get("dep")), _hm(row.get("arr"))
    if not (dep and arr):
        return ""
    fno = str(row.get("fno") or "").split("/")[0].strip().upper()
    return " · {f}{dep}–{arr}".format(
        f=fno + " " if fno else "", dep=dep, arr=arr)


def history_board(history, sched=None):
    """v0.62: leaderboard rows for the cabin UI - one per watched leg.

    The ring history already stores every observation, but the card
    needs the derived story: the all-time low WITH its fare date (when
    is that cheapest ticket for), the latest observation, and how far
    the market now sits above its own record. Latest = max ts (the
    collector rewrites same-date entries, so ts orders observations),
    tie-broken by date. Legs without a single numeric price are
    skipped. Sorted by low asc so the best departure city leads.
    Pure."""
    rows = []
    for rid, r in (history.get("routes") or {}).items():
        obs = [o for o in (r.get("obs") or [])
               if isinstance(o.get("price"), (int, float))]
        if not obs:
            continue
        low = min(obs, key=lambda o: o["price"])
        latest = max(obs, key=lambda o: (o.get("ts") or "",
                                         o.get("date") or ""))
        rows.append({
            "route_id": rid,
            "from_city": r.get("from_city", ""),
            "to_city": r.get("to_city", ""),
            "low": low["price"],
            "low_date": low.get("date", ""),
            "low_fno": low.get("fno", ""),
            "latest": latest["price"],
            "latest_date": latest.get("date", ""),
            "gap": round(float(latest["price"]) - float(low["price"]), 2),
            "samples": len(obs),
            # v1.30: which source owns the record low + how many
            # observations are qunar-precise, so the board can show
            # whether a leg's story is ground truth or estimate.
            "low_src": low.get("src") or "",
            "precise": sum(1 for o in obs
                           if src_class(o.get("src")) >= 2),
        })
        if sched:
            low_row = {"date": rows[-1]["low_date"],
                       "fno": rows[-1]["low_fno"]}
            if borrow_sched_time(low_row, sched,
                                 rows[-1]["from_city"],
                                 rows[-1]["to_city"]):
                rows[-1]["low_dep"] = low_row["dep"]
                rows[-1]["low_arr"] = low_row["arr"]
                rows[-1]["low_tsrc"] = low_row["tsrc"]
    rows.sort(key=lambda x: x["low"])
    return rows


def history_timetable(history, per_leg=8, sched=None):
    """v1.11: cheapest per-flight rows per leg for the new cabin tab.

    Each leg's ring history contributes its N cheapest fno-carrying
    observations (price asc, tie on date) - the cabin tab renders
    them as a per-flight timetable: WHICH business flight, WHEN it
    departs, for how much. v1.10 started persisting dep/arr on new
    observations; legacy fno-less rows stay board-only. Legs sort by
    their cheapest row so the best city leads. Pure."""
    groups = []
    for rid, r in (history.get("routes") or {}).items():
        obs = [o for o in (r.get("obs") or [])
               if isinstance(o.get("price"), (int, float))]
        rows = [o for o in obs if (o.get("fno") or "")]
        # v1.14: per (date, fno) dedup - a timed observation UPGRADES
        # its timeless twin of the same flight. Without this a cheap
        # timeless legacy row outranks every newer timed obs of the
        # same flight by price forever, so the refill never becomes
        # visible in the top-N table.
        best = {}
        for o in rows:
            key = (o.get("date") or "", o.get("fno") or "")
            timed = bool((o.get("dep") or "") and (o.get("arr") or ""))
            cur = best.get(key)
            if cur is None:
                best[key] = o
                continue
            cur_timed = bool((cur.get("dep") or "")
                             and (cur.get("arr") or ""))
            if timed and not cur_timed:
                best[key] = o
            elif timed == cur_timed and o["price"] < cur["price"]:
                best[key] = o
        rows = sorted(best.values(),
                      key=lambda o: (o["price"], o.get("date") or ""))
        # v1.12: per-date lowest price series for the leg sparkline -
        # any observation qualifies (fno-less legacy rows still carry
        # a real price), dates ascending, newest N=30 points.
        by_date = {}
        for o in obs:
            d = str(o.get("date") or "")
            if d and (d not in by_date
                      or o["price"] < by_date[d]):
                by_date[d] = o["price"]
        spark = [{"d": d, "p": by_date[d]}
                 for d in sorted(by_date)][-30:]
        top = rows[:per_leg]
        # v1.14: time coverage of the shown rows - the UI renders a
        # "timed x/y" chip so the refill progress is visible.
        timed = sum(1 for o in top
                    if (o.get("dep") or "") and (o.get("arr") or ""))
        borrowed = 0
        if sched:
            for o in top:
                if borrow_sched_time(o, sched,
                                     r.get("from_city", ""),
                                     r.get("to_city", "")):
                    borrowed += 1
            if borrowed:
                timed = sum(1 for o in top
                            if (o.get("dep") or "")
                            and (o.get("arr") or ""))
        groups.append({
            "route_id": rid,
            "from_city": r.get("from_city", ""),
            "to_city": r.get("to_city", ""),
            "spark": spark,
            "timed": timed,
            "total": len(top),
            "borrowed": borrowed,
            # v1.30: precise pay-total coverage of the shown rows.
            "precise": sum(1 for o in top
                           if src_class(o.get("src")) >= 2),
            "rows": [{"date": o.get("date") or "",
                      "fno": o.get("fno") or "",
                      "dep": o.get("dep") or "",
                      "arr": o.get("arr") or "",
                      "cross_day": bool(o.get("cross_day")),
                      "src": o.get("src") or "",
                      "tsrc": o.get("tsrc")
                              or ("patrol" if (o.get("dep") or "")
                                  and (o.get("arr") or "") else ""),
                      "price": o["price"]} for o in top],
        })
    groups.sort(key=lambda g: (g["rows"][0]["price"]
                               if g["rows"] else 1e18))
    return groups


def cooldown_ok(last_alert_at, cw, now=None):
    """True when a new alert may fire given the previous fire time."""
    hours = float(cw.get("cooldown_hours") or 0)
    if not last_alert_at or hours <= 0:
        return True
    now = now or datetime.now()
    try:
        prev = datetime.fromisoformat(last_alert_at)
    except (TypeError, ValueError):
        return True
    return (now - prev).total_seconds() >= hours * 3600
