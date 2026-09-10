# -*- coding: utf-8 -*-
"""M3: reverse destination search - budget-first "where can I go".

给定出发城市 + 预算, 在候选目的地带里逐个查去哪儿价格日历,
返回窗口内最低真实含税价 <= 预算的目的地列表(按价格升序)。

约束(合规红线):
- 每次搜索的实发请求数有硬预算(默认 8, 上限 15), 失败不重试;
- 候选结果走文件缓存(TTL 6h), 命中缓存不消耗请求预算;
- 只统计真实价(qunar-calendar), 估算/参考价一律不参与。
"""
import datetime as dt
import json
import os
import time

from core.alerts import total_price
from core.cities import CITIES
from core.flights import airline_name, fetch_calendar

REVERSE_CACHE_FILE = "reverse_cache.json"
REVERSE_CACHE_TTL = 6 * 3600
DEFAULT_MAX_REQUESTS = 8
HARD_MAX_REQUESTS = 15
POLITE_SLEEP_S = 1.2


def candidate_pool(from_city, cities=None):
    """Destination candidates: curated city list minus origin."""
    names = [c["name"] for c in (cities if cities is not None else CITIES)]
    return [n for n in names if n and n != from_city]


def _load_cache(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def _save_cache(path, cache):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception:
        pass


def reverse_search(session, net_cfg, tax_cfg, from_city, budget,
                   date_from, date_to, pool=None, max_requests=None,
                   data_dir="data", sleep_s=POLITE_SLEEP_S, rec=None,
                   fetch=None, now_ts=None):
    """Scan candidates under a hard request budget; return in-budget hits.

    fetch is injectable for tests (defaults to core.flights.fetch_calendar).
    Result: {from_city, budget, window, searched, cached_hits, requests_used,
             failed, hits: [{city, total_price, bare_price, date, flight_no,
                             airline, url, cached, ts}], generated_at}
    """
    from_city = (from_city or "").strip()
    budget = float(budget)
    if not from_city:
        raise ValueError("from_city required")
    if budget <= 0:
        raise ValueError("budget must be positive")
    max_req = min(int(max_requests or DEFAULT_MAX_REQUESTS), HARD_MAX_REQUESTS)
    fetch = fetch or fetch_calendar
    now_ts = now_ts if now_ts is not None else time.time()
    cache_path = os.path.join(data_dir, REVERSE_CACHE_FILE)
    cache = _load_cache(cache_path)
    pool = pool if pool is not None else candidate_pool(from_city)

    hits, failed, requests_used, scanned = [], 0, 0, 0
    for city in pool:
        if requests_used >= max_req:
            break
        key = "%s->%s|%s~%s" % (from_city, city, date_from, date_to)
        ent = cache.get(key)
        is_cached = bool(ent and now_ts - float(ent.get("ts", 0)) < REVERSE_CACHE_TTL)
        if not is_cached:
            t0 = time.time()
            try:
                deals = fetch(session, net_cfg, from_city, city,
                              date_from, date_to)
                requests_used += 1
                best = min(deals, key=lambda d: d.bare_price) if deals else None
                if best is None:
                    ent = {"ts": now_ts, "no_data": True}
                else:
                    ent = {"ts": now_ts, "bare": best.bare_price,
                           "date": best.date, "flight_no": best.flight_no,
                           "url": best.url}
                cache[key] = ent
                if rec:
                    rec.step("qunar-calendar", city, "reverse scan", "ok",
                             (time.time() - t0) * 1000,
                             count=len(deals), cached=False)
            except Exception as e:
                requests_used += 1
                failed += 1
                if rec:
                    rec.step("qunar-calendar", city, "reverse scan", "error",
                             (time.time() - t0) * 1000, error=e)
                time.sleep(sleep_s)
                continue
            time.sleep(sleep_s)
        scanned += 1
        if ent.get("no_data"):
            continue
        total = total_price(float(ent["bare"]), tax_cfg)
        if total <= budget:
            code = (ent.get("flight_no") or "")[:2].upper()
            hits.append({"city": city, "total_price": int(round(total)),
                         "bare_price": float(ent["bare"]),
                         "date": ent.get("date", ""),
                         "flight_no": ent.get("flight_no", ""),
                         "airline": airline_name(code) if code else "",
                         "url": ent.get("url", ""),
                         "cached": is_cached,
                         "ts": ent.get("ts")})
    _save_cache(cache_path, cache)
    hits.sort(key=lambda h: (h["total_price"], h["city"]))
    return {"from_city": from_city, "budget": budget,
            "window": {"from": date_from, "to": date_to},
            "pool_size": len(pool), "scanned": scanned,
            "requests_used": requests_used, "failed": failed,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "hits": hits}
