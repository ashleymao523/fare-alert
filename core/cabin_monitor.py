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
        "watch_from_cities": [],
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


def record_low(history, route_id, from_city, to_city, cabin, date, price_total):
    """Insert one business-cabin observation; ring-cap per route.
    Same-date same-cabin observations replace (latest wins)."""
    routes = history.setdefault("routes", {})
    r = routes.setdefault(route_id, {
        "from_city": from_city, "to_city": to_city,
        "obs": [], "lowest": None,
    })
    r["from_city"] = from_city or r.get("from_city", "")
    r["to_city"] = to_city or r.get("to_city", "")
    obs = r.setdefault("obs", [])
    obs[:] = [o for o in obs
              if not (o.get("date") == date and o.get("cabin") == cabin)]
    obs.append({"date": date, "cabin": cabin, "price": price_total,
                "ts": datetime.now().strftime("%Y-%m-%dT%H:%M")})
    obs.sort(key=lambda o: o.get("date") or "")
    if len(obs) > HISTORY_CAP:
        del obs[:len(obs) - HISTORY_CAP]
    lows = [o["price"] for o in obs
            if isinstance(o.get("price"), (int, float))]
    r["lowest"] = min(lows) if lows else None
    return r


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
