# -*- coding: utf-8 -*-
"""v0.42: business-cabin low-fare collector + alert."""
from __future__ import annotations

import json
import os
from datetime import datetime

HISTORY_CAP = 120


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


def record_low(history, route_id, from_city, to_city, cabin, date, price_total):
    """Insert one business-cabin observation; ring-cap per route.
    Same-date same-cabin observations replace (latest wins).
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
    obs[:] = [o for o in obs
              if not (o.get("date") == date and o.get("cabin") == cabin)]
    entry = {"date": date, "cabin": cabin, "price": price_total,
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
            "latest": latest["price"],
            "latest_date": latest.get("date", ""),
            "gap": round(float(latest["price"]) - float(low["price"]), 2),
            "samples": len(obs),
        })
    rows.sort(key=lambda x: x["low"])
    return rows


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
