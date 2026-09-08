# -*- coding: utf-8 -*-
"""Flight price source: Qunar low-price calendar gateway (no auth needed)."""
import urllib.parse

import requests

from .models import FlightDeal

CALENDAR_URL = "https://gw.flight.qunar.com/api/f/priceCalendar"

AIRLINE_NAMES = {
    "3U": "四川航空", "CA": "中国国际航空", "MU": "中国东方航空",
    "CZ": "中国南方航空", "MF": "厦门航空", "HO": "吉祥航空",
    "ZH": "深圳航空", "FM": "上海航空", "SC": "山东航空",
    "EU": "成都航空", "G5": "华夏航空", "DZ": "东海航空",
    "TV": "西藏航空", "GJ": "长龙航空", "PN": "西部航空",
    "GS": "天津航空", "8L": "祥鹏航空", "KN": "中国联合航空",
    "9C": "春秋航空", "AQ": "九元航空", "JR": "瑞丽航空",
}


def airline_name(code):
    return AIRLINE_NAMES.get(code, code or "未知航司")


def booking_url(from_city, to_city, date):
    q = urllib.parse.urlencode({
        "fromCity": from_city,
        "toCity": to_city,
        "fromDate": date,
        "toDate": "",
        "child": "0",
        "baby": "0",
        "cabinType": "0",
    })
    return "https://m.flight.qunar.com/h5/flight/oneway?" + q


def fetch_calendar(session, net_cfg, from_city, to_city, date_from, date_to):
    """Return sorted list[FlightDeal] within [date_from, date_to]."""
    headers = {
        "User-Agent": net_cfg.get("user_agent_mobile", "Mozilla/5.0"),
        "Referer": "https://m.flight.qunar.com/",
        "Accept": "application/json",
    }
    r = session.get(
        CALENDAR_URL,
        params={"dep": from_city, "arr": to_city, "days": "", "priceType": "1"},
        headers=headers,
        timeout=net_cfg.get("timeout_seconds", 25),
    )
    r.raise_for_status()
    j = r.json()
    status = (j.get("bstatus") or {}).get("code")
    if status != 0 or not j.get("data"):
        raise RuntimeError("qunar calendar bad response: " + str(j)[:200])
    deals = []
    for e in j["data"].get("gflights") or []:
        d = e.get("date", "")
        p = e.get("price", "")
        code = e.get("code", "")
        if not d or not p:
            continue
        if not (date_from <= d <= date_to):
            continue
        try:
            bare = float(p)
        except (TypeError, ValueError):
            continue
        deals.append(FlightDeal(
            date=d,
            bare_price=bare,
            flight_no=code,
            url=booking_url(from_city, to_city, d),
        ))
    deals.sort(key=lambda x: (x.bare_price, x.date))
    return deals


def window_dates(date_from, date_to):
    """All ISO dates in [date_from, date_to]."""
    import datetime
    out, cur = [], datetime.date.fromisoformat(date_from)
    end = datetime.date.fromisoformat(date_to)
    while cur <= end:
        out.append(cur.isoformat())
        cur += datetime.timedelta(days=1)
    return out


def merge_fill_deals(qunar_deals, ama_deals, booking_url_fn):
    """Fill calendar gaps using Amadeus fallback deals.

    Only dates missing from the qunar calendar are taken from ama_deals
    (source tagged 'amadeus-fill'); the purchase url is rewritten to the
    domestic OTA page so the click-through stays useful for CN users.
    Returns the merged, price-sorted list.
    """
    have = {d.date for d in qunar_deals}
    filled = []
    for d in ama_deals:
        if d.date in have:
            continue
        d.source = "amadeus-fill"
        d.url = booking_url_fn(d.date)
        filled.append(d)
    merged = list(qunar_deals) + filled
    merged.sort(key=lambda x: (x.bare_price, x.date))
    return merged, len(filled)
