# -*- coding: utf-8 -*-
"""v0.42: business-cabin low-fare collector + alert."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from .booking_fill import DEFAULT_FX
from .models import FlightDeal

HISTORY_CAP = 300


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
            return obj
    except (OSError, ValueError):
        pass
    return {"routes": {}}


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
            hid = "point-%s-%s" % (fc, tc)
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
               price_total, fno="", dep="", arr=""):
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
    obs[:] = [o for o in obs
              if not (o.get("date") == date and o.get("cabin") == cabin
                      and (o.get("fno") or "") == fno)]
    entry = {"date": date, "cabin": cabin, "price": price_total,
             "fno": fno,
             "dep": str(dep or ""), "arr": str(arr or ""),
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


def probe_dates(history, route_id, date_from, date_to, k=6):
    """v1.09: which dates deserve the next keyless BUSINESS probe.

    Every date in the window sorts by its last observation ts -
    never-probed ('') first, then stalest; ties break on the earlier
    date. Taking the head rotates the whole window over successive
    rounds with zero extra state: a restart simply resumes from
    whatever the history ring says. Pure function."""
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
    seen = {}
    route = ((history or {}).get("routes") or {}).get(route_id) or {}
    for o in route.get("obs") or []:
        d = str(o.get("date") or "")
        ts = str(o.get("ts") or "")
        if d and (d not in seen or ts > seen[d]):
            seen[d] = ts
    days.sort(key=lambda d: (seen.get(d, ""), d))
    return days[:k]


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
    threshold = cw.get("threshold_total") or 0
    if not threshold:
        return []
    hits = []
    for rid, r in (history.get("routes") or {}).items():
        obs = r.get("obs") or []
        if not obs:
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
            })
    return hits


def history_board(history):
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
        })
    rows.sort(key=lambda x: x["low"])
    return rows


def history_timetable(history, per_leg=8):
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
        rows.sort(key=lambda o: (o["price"], o.get("date") or ""))
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
        groups.append({
            "route_id": rid,
            "from_city": r.get("from_city", ""),
            "to_city": r.get("to_city", ""),
            "spark": spark,
            "rows": [{"date": o.get("date") or "",
                      "fno": o.get("fno") or "",
                      "dep": o.get("dep") or "",
                      "arr": o.get("arr") or "",
                      "price": o["price"]} for o in rows[:per_leg]],
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
