# -*- coding: utf-8 -*-
"""Amadeus Self-Service: cheapest-date search for international flight calendars.

Free test tier (developers.amadeus.com) is enough for personal low-fare alerts:
one call covers a whole date range with tax-included lowest price per day.
"""
import json
import os
import time
import urllib.parse

from .alerts import tax_amount
from .models import FlightDeal

BASE_URLS = {
    "test": "https://test.api.amadeus.com",
    "prod": "https://api.amadeus.com",
}
TOKEN_FILE = "amadeus_token.json"
USAGE_FILE = "amadeus_usage.json"


def _bump_usage(data_dir, n=1):
    """v0.44: daily Amadeus call counter (quota transparency)."""
    if not data_dir:
        return 0
    path = os.path.join(data_dir, USAGE_FILE)
    day = time.strftime("%Y-%m-%d")
    days = {}
    try:
        with open(path, encoding="utf-8") as f:
            days = (json.load(f) or {}).get("days") or {}
    except Exception:
        days = {}
    days[day] = int(days.get(day, 0)) + int(n)
    for k in sorted(days)[:-14]:  # keep a rolling 14-day window
        del days[k]
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"days": days}, f, ensure_ascii=False)
    except Exception:
        pass
    return days[day]


def usage_snapshot(data_dir):
    """Today's call count + the rolling daily history."""
    path = os.path.join(data_dir, USAGE_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            days = (json.load(f) or {}).get("days") or {}
    except Exception:
        days = {}
    today = time.strftime("%Y-%m-%d")
    return {"today": int(days.get(today, 0)), "days": days}


def _api_get(session, url, data_dir, **kw):
    """session.get + daily usage accounting."""
    _bump_usage(data_dir)
    return session.get(url, **kw)


def _base_url(ama_cfg):
    return BASE_URLS.get((ama_cfg.get("env") or "test").lower(), BASE_URLS["test"])


def get_token(session, net_cfg, ama_cfg, data_dir):
    """OAuth2 client-credentials token, cached in data/amadeus_token.json."""
    cid = (ama_cfg.get("client_id") or "").strip()
    csec = (ama_cfg.get("client_secret") or "").strip()
    if not cid or not csec:
        raise RuntimeError("Amadeus client_id/client_secret 未配置")
    path = os.path.join(data_dir, TOKEN_FILE)
    now = time.time()
    try:
        with open(path, encoding="utf-8") as f:
            tok = json.load(f)
        if tok.get("client_id") == cid and float(tok.get("expires_at", 0)) > now + 120:
            return tok["access_token"]
    except Exception:
        pass
    r = session.post(
        _base_url(ama_cfg) + "/v1/security/oauth2/token",
        data={"grant_type": "client_credentials",
              "client_id": cid, "client_secret": csec},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=net_cfg.get("timeout_seconds", 25),
    )
    r.raise_for_status()
    j = r.json()
    token = (j.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Amadeus token 响应异常: " + str(j)[:160])
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"client_id": cid, "access_token": token,
                       "expires_at": now + int(j.get("expires_in", 1799))}, f)
    except Exception:
        pass
    return token


def google_flights_url(from_iata, to_iata, date):
    q = urllib.parse.urlencode(
        {"q": "Flights from {} to {} on {}".format(from_iata, to_iata, date)})
    return "https://www.google.com/travel/flights?" + q


def _cabin_offer_times(off):
    """v0.43: exact dep/arr clock times from a flight-offers offer.

    itineraries[0].segments carry local departure.at / arrival.at per
    segment (ISO datetime); first/last segment bound the journey.
    Returns (flight_no, dep, arr, duration_text, transfer_iata).
    """
    it = ((off.get("itineraries") or [{}])[0]) or {}
    segs = it.get("segments") or []
    if not segs:
        return "", "", "", "", ""
    nos = []
    for s in segs:
        nos.append(((s.get("carrierCode") or "")
                    + str(s.get("number") or "")).strip())
    dep_at = ((segs[0].get("departure") or {}).get("at")) or ""
    arr_at = ((segs[-1].get("arrival") or {}).get("at")) or ""
    dur = (it.get("duration") or "").replace("PT", "") \
        .replace("H", "h").replace("M", "m")
    stop = ""
    if len(segs) > 1:
        stop = ((segs[-2].get("arrival") or {}).get("iataCode")) or ""
    return "/".join(nos), dep_at[11:16], arr_at[11:16], dur, stop


def _best_offer(j):
    """Cheapest parseable data[] offer; returns (total, offer) or None."""
    best = None
    for off in (j.get("data") or [])[:3]:
        total = (((off.get("price") or {}).get("grandTotal")) or "")
        try:
            total = float(total)
        except (TypeError, ValueError):
            continue
        if best is None or total < best[0]:
            best = (total, off)
    return best


def fetch_cabin_offers(session, net_cfg, ama_cfg, tax_cfg,
                       from_iata, to_iata, date_from, date_to,
                       cabin="business", data_dir=None, max_days=8):
    """v0.42: per-cabin lowest offers via flight-offers-search.

    The cheapest-dates calendar only returns the economy floor, so the
    business-cabin watch needs real offers. We probe up to max_days
    spread dates in the window (start/mid/end) with travelClass pinned:
    quota-friendly (<=3 calls per route) while still catching typical
    business-cabin lows. Returns FlightDeal rows with cabin set and
    source='amadeus-cabin'.
    """
    token = get_token(session, net_cfg, ama_cfg, data_dir)
    spread = _spread_dates(date_from, date_to, max_days)
    deals = []
    for d in spread:
        params = {
            "originLocationCode": from_iata,
            "destinationLocationCode": to_iata,
            "departureDate": d,
            "adults": 1,
            "travelClass": (cabin or "business").upper(),
            "currencyCode": "CNY",
            "max": 3,
        }
        r = _api_get(
            session, _base_url(ama_cfg) + "/v2/shopping/flight-offers",
            data_dir,
            params=params,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/json"},
            timeout=net_cfg.get("timeout_seconds", 25),
        )
        r.raise_for_status()
        j = r.json()
        if "errors" in j:
            continue
        best = _best_offer(j)
        if best:
            fn, dep, arr, dur, stop = _cabin_offer_times(best[1])
            deals.append(FlightDeal(
                date=d, bare_price=round(best[0], 1), flight_no=fn,
                dep_time=dep, arr_time=arr, duration_text=dur,
                time_src="amadeus" if dep else "",
                dep_src="amadeus" if dep else "",
                arr_src="amadeus" if arr else "",
                stop_kind="transfer" if stop else "",
                stop_city=stop,
                source="amadeus-cabin", cabin=cabin,
                url=google_flights_url(from_iata, to_iata, d)))
    deals.sort(key=lambda x: (x.bare_price, x.date))
    return deals


def fetch_fill_offers(session, net_cfg, ama_cfg, tax_cfg,
                      from_iata, to_iata, gap_dates, data_dir,
                      max_days=6):
    """v0.44: offer-exact last resort for economy calendar holes.

    The cheapest-dates calendar carries prices only. For the few dates
    it also missed, probe each with flight-offers (ECONOMY, max=3) to
    get price + exact dep/arr + flight numbers in one shot. Prices are
    tax-inclusive grand totals, converted to the same virtual bare
    price the domestic pipeline expects. Returns rows already tagged
    source='amadeus-fill' (url is rewritten by merge_fill_deals).
    """
    token = get_token(session, net_cfg, ama_cfg, data_dir)
    tax = tax_amount(tax_cfg)
    deals = []
    for d in [x for x in (gap_dates or []) if x][:max_days]:
        params = {
            "originLocationCode": from_iata,
            "destinationLocationCode": to_iata,
            "departureDate": d,
            "adults": 1,
            "travelClass": "ECONOMY",
            "currencyCode": "CNY",
            "max": 3,
        }
        r = _api_get(
            session, _base_url(ama_cfg) + "/v2/shopping/flight-offers",
            data_dir,
            params=params,
            headers={"Authorization": "Bearer " + token,
                     "Accept": "application/json"},
            timeout=net_cfg.get("timeout_seconds", 25),
        )
        r.raise_for_status()
        j = r.json()
        if "errors" in j:
            continue
        best = _best_offer(j)
        if not best:
            continue
        fn, dep, arr, dur, stop = _cabin_offer_times(best[1])
        deals.append(FlightDeal(
            date=d, bare_price=round(best[0] - tax, 1), flight_no=fn,
            dep_time=dep, arr_time=arr, duration_text=dur,
            time_src="amadeus" if dep else "",
            dep_src="amadeus" if dep else "",
            arr_src="amadeus" if arr else "",
            stop_kind="transfer" if stop else "",
            stop_city=stop,
            source="amadeus-fill", url=""))
    deals.sort(key=lambda x: (x.bare_price, x.date))
    return deals


def _spread_dates(date_from, date_to, max_days):
    """Evenly pick <=max_days dates inside the window (ISO strings)."""
    from datetime import date, timedelta
    try:
        a = date.fromisoformat(date_from)
        b = date.fromisoformat(date_to)
    except (TypeError, ValueError):
        return []
    span = (b - a).days
    if span < 0:
        return []
    if span + 1 <= max_days:
        step = 1
    else:
        step = max(1, span // max(1, max_days - 1))
    out = []
    cur = a
    while cur <= b and len(out) < max_days:
        out.append(cur.isoformat())
        cur = cur + timedelta(days=step)
    return out


def fetch_intl_calendar(session, net_cfg, ama_cfg, tax_cfg,
                        from_iata, to_iata, date_from, date_to, data_dir):
    """Return sorted list[FlightDeal] within [date_from, date_to].

    Amadeus price.total is the tax-included total, so we convert to a
    'virtual bare price' (total - configured tax) to keep total_price()
    semantics identical to the domestic qunar source.
    """
    token = get_token(session, net_cfg, ama_cfg, data_dir)
    params = {"origin": from_iata.upper(), "destination": to_iata.upper(),
              "oneWay": "true"}
    currency = (ama_cfg.get("currency") or "").strip()
    if currency:
        params["currency"] = currency.upper()
    r = _api_get(
        session, _base_url(ama_cfg) + "/v1/shopping/flight-dates/cheapest",
        data_dir,
        params=params,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
        timeout=net_cfg.get("timeout_seconds", 25),
    )
    r.raise_for_status()
    j = r.json()
    if "errors" in j:
        msg = "; ".join(e.get("detail", "") or e.get("title", "")
                        for e in j["errors"])[:200]
        raise RuntimeError("Amadeus错误: " + msg)
    tax = tax_amount(tax_cfg)
    deals = []
    for e in j.get("data") or []:
        d = e.get("departureDate") or ""
        total = ((e.get("price") or {}).get("total")) or ""
        if not d or not total or not (date_from <= d <= date_to):
            continue
        try:
            total = float(total)
        except (TypeError, ValueError):
            continue
        deals.append(FlightDeal(
            date=d,
            bare_price=round(total - tax, 1),
            flight_no="",
            source="amadeus-intl",
            url=google_flights_url(from_iata, to_iata, d),
        ))
    deals.sort(key=lambda x: (x.bare_price, x.date))
    return deals


# Major CN city -> IATA (city code where possible) for domestic gap-filling.
CITY_IATA = {
    "北京": "BJS", "上海": "SHA", "广州": "CAN", "深圳": "SZX",
    "成都": "CTU", "重庆": "CKG", "杭州": "HGH", "西安": "SIA",
    "昆明": "KMG", "厦门": "XMN", "长沙": "CSX", "武汉": "WUH",
    "南京": "NKG", "青岛": "TAO", "天津": "TSN", "海口": "HAK",
    "三亚": "SYX", "郑州": "CGO", "济南": "TNA", "福州": "FOC",
    "贵阳": "KWE", "南宁": "NNG", "桂林": "KWL", "兰州": "LHW",
    "乌鲁木齐": "URC", "哈尔滨": "HRB", "沈阳": "SHE", "大连": "DLC",
    "长春": "CGQ", "太原": "TYN", "石家庄": "SJW", "合肥": "HFE",
    "南昌": "KHN", "温州": "WNZ", "宁波": "NGB", "无锡": "WUX",
    "泉州": "JJN", "珠海": "ZUH", "汕头": "SWA", "呼和浩特": "HET",
    "银川": "INC", "西宁": "XNN", "拉萨": "LXA", "烟台": "YNT",
    "威海": "WEH", "徐州": "XUZ", "常州": "CZX", "扬州": "YTY",
    "舟山": "HSN", "义乌": "YIW", "丽江": "LJG", "大理": "DLU",
    "西双版纳": "JHG", "敦煌": "DNH", "张家界": "DYX", "绵阳": "MIG",
    "宜昌": "YIH", "襄阳": "XFN", "湛江": "ZHA", "中山": "ZGN",
}


def city_iata(city):
    """Resolve a CN city name to an IATA city/airport code, or None."""
    c = (city or "").strip().replace("市", "")
    return CITY_IATA.get(c)


SCHEDULE_CACHE = "amadeus_schedule_cache.json"
SCHEDULE_TTL = 14 * 86400  # 航班排班按航季更新, 14 天缓存省配额


def fetch_schedule_times(session, net_cfg, ama_cfg, from_iata, to_iata,
                         date_from, date_to, data_dir):
    """Dep/arr times for a route via Amadeus ONB schedule search.

    One call per month covers every day of that month (quota-friendly).
    Returns a flat list of schedule rows [{n, dep, arr, dur}, ...];
    matching by flight number is done by the caller. Best-effort:
    silently returns [] on any error.
    """
    token = get_token(session, net_cfg, ama_cfg, data_dir)
    import datetime as _dt
    import hashlib
    d0 = _dt.date.fromisoformat(date_from)
    d1 = _dt.date.fromisoformat(date_to)
    months = []
    cur = _dt.date(d0.year, d0.month, 1)
    while cur <= d1:
        months.append(cur.strftime("%Y-%m"))
        cur = _dt.date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
    path = os.path.join(data_dir, SCHEDULE_CACHE)
    now = time.time()
    cache = {}
    try:
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        pass
    out = []
    for month in months:
        key = "{}-{}-{}".format(from_iata.upper(), to_iata.upper(), month)
        ent = cache.get(key)
        if not (ent and now - float(ent.get("ts", 0)) < SCHEDULE_TTL):
            try:
                r = _api_get(
                    session, _base_url(ama_cfg) + "/v1/schedules",
                    data_dir,
                    params={"origin": from_iata.upper(),
                            "destination": to_iata.upper(),
                            "month": month},
                    headers={"Authorization": "Bearer " + token,
                             "Accept": "application/json"},
                    timeout=net_cfg.get("timeout_seconds", 25),
                )
                r.raise_for_status()
                j = r.json()
                if "errors" in j:
                    raise RuntimeError(j["errors"][0].get("detail", "")[:120])
                rows = []
                for it in j.get("data") or []:
                    sch = it.get("flight") or {}
                    dep = sch.get("departure") or {}
                    arr = sch.get("arrival") or {}
                    if not (dep.get("airport") and arr.get("airport")):
                        continue
                    rows.append({
                        "n": ((sch.get("carrierCode") or "")
                              + (sch.get("number") or "")).strip(),
                        "dep": dep.get("scheduledTime", "")[11:16],
                        "arr": arr.get("scheduledTime", "")[11:16],
                        "dur": (sch.get("duration") or "").replace("PT", "")
                               .replace("H", "h").replace("M", "m"),
                        "from_ap": dep.get("airport"),
                        "to_ap": arr.get("airport"),
                    })
                cache[key] = {"ts": now, "rows": rows}
                ent = cache[key]
                try:
                    os.makedirs(data_dir, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False)
                except Exception:
                    pass
            except Exception:
                continue
        out.extend(ent.get("rows", []))
    return out
