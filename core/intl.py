# -*- coding: utf-8 -*-
"""Amadeus Self-Service: cheapest-date search for international flight calendars.

Free test tier (developer.amadeus.com) is enough for personal low-fare alerts:
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
    r = session.get(
        _base_url(ama_cfg) + "/v1/shopping/flight-dates/cheapest",
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
