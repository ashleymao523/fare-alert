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

# Airport coordinates (lat, lon) for duration estimation.
# CN domestic + common intl hubs reachable from CN. Add freely as needed.
AIRPORT_COORDS = {
    "PEK": (40.08, 116.58), "PKX": (39.51, 116.41), "BJS": (40.08, 116.58),
    "SHA": (31.20, 121.34), "PVG": (31.14, 121.80), "CAN": (23.39, 113.30),
    "SZX": (22.64, 113.81), "CTU": (30.58, 103.95), "TFU": (30.31, 104.44),
    "CKG": (29.72, 106.64), "HGH": (30.23, 120.43), "SIA": (34.45, 108.75),
    "XIY": (34.45, 108.75), "KMG": (25.10, 102.93), "XMN": (24.54, 118.13),
    "CSX": (28.19, 113.22), "WUH": (30.78, 114.21), "NKG": (31.74, 118.86),
    "TAO": (36.37, 120.08), "TSN": (39.12, 117.35), "HAK": (19.93, 110.46),
    "SYX": (18.30, 109.41), "CGO": (34.52, 113.84), "TNA": (36.86, 117.22),
    "FOC": (25.93, 119.66), "KWE": (26.54, 106.80), "NNG": (22.61, 108.17),
    "KWL": (25.22, 110.04), "LHW": (36.52, 103.62), "URC": (43.91, 87.47),
    "HRB": (45.62, 126.60), "SHE": (41.64, 123.48), "DLC": (38.96, 121.54),
    "CGQ": (43.99, 125.69), "TYN": (37.75, 112.63), "SJW": (38.28, 114.70),
    "HFE": (31.78, 116.98), "KHN": (28.86, 115.90), "WNZ": (27.91, 120.85),
    "NGB": (29.83, 121.46), "WUX": (31.49, 120.43), "JJN": (24.80, 118.59),
    "ZUH": (22.01, 113.38), "SWA": (23.43, 116.68), "HET": (40.85, 111.82),
    "INC": (38.32, 106.39), "XNN": (36.53, 102.04), "LXA": (29.30, 90.91),
    "YNT": (37.40, 121.37), "WEH": (37.19, 122.23), "XUZ": (34.06, 117.56),
    "CZX": (31.92, 119.78), "YTY": (32.56, 119.72), "HSN": (29.94, 122.36),
    "YIW": (29.34, 120.03), "LJG": (26.68, 100.25), "DLU": (25.65, 100.32),
    "JHG": (21.97, 100.76), "DNH": (40.51, 94.81), "DYX": (29.10, 110.24),
    "MIG": (31.43, 104.68), "YIH": (30.67, 111.44), "XFN": (32.15, 112.29),
    "ZHA": (21.21, 110.36), "ZGN": (22.60, 113.35),
    # intl hubs
    "HKG": (22.31, 113.91), "MFM": (22.15, 113.59), "TPE": (25.08, 121.23),
    "BKK": (13.69, 100.75), "DMK": (13.91, 100.61), "HKT": (8.11, 98.31),
    "CNX": (18.77, 98.96), "NRT": (35.77, 140.39), "HND": (35.55, 139.78),
    "KIX": (34.43, 135.23), "ITM": (34.79, 135.44), "CTS": (42.78, 141.69),
    "FUK": (33.59, 130.45), "ICN": (37.46, 126.44), "GMP": (37.56, 126.79),
    "SIN": (1.36, 103.99), "KUL": (2.75, 101.71), "PEN": (5.30, 100.28),
    "SGN": (10.82, 106.65), "HAN": (21.22, 105.81), "DAD": (16.04, 108.20),
    "DPS": (-8.75, 115.17), "MNL": (14.51, 121.02), "CEB": (10.31, 123.98),
    "DXB": (25.25, 55.36), "DOH": (25.27, 51.61), "AUH": (24.43, 54.65),
    "IST": (41.26, 28.74), "SVO": (55.97, 37.41), "CDG": (49.01, 2.55),
    "ORY": (48.73, 2.38), "LHR": (51.47, -0.46), "LGW": (51.15, -0.19),
    "FRA": (50.04, 8.56), "MUC": (48.35, 11.79), "AMS": (52.31, 4.76),
    "MAD": (40.47, -3.56), "BCN": (41.30, 2.08), "FCO": (41.80, 12.25),
    "MXP": (45.63, 8.72), "ZRH": (47.46, 8.55), "VIE": (48.11, 16.57),
    "CPH": (55.62, 12.66), "ARN": (59.65, 17.92), "HEL": (60.32, 24.96),
    "JFK": (40.64, -73.78), "LAX": (33.94, -118.41), "SFO": (37.62, -122.38),
    "SYD": (-33.94, 151.18), "MEL": (-37.67, 144.84), "AKL": (-37.01, 174.79),
}


def _haversine_km(a, b):
    import math
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def estimate_duration_text(from_code, to_code, connecting=False):
    """Honest great-circle estimate: ~750km/h cruise + 40min taxi/queue.
    Returns '' when coordinates unknown. connecting adds typical 2.5h layover.
    """
    a = AIRPORT_COORDS.get((from_code or "").upper())
    b = AIRPORT_COORDS.get((to_code or "").upper())
    if not a or not b:
        return ""
    hours = _haversine_km(a, b) / 750.0 + 0.7
    if connecting:
        hours += 2.5
    m = max(60, int(round(hours * 60 / 5.0)) * 5)
    return "约{}h{:02d}m(估)".format(m // 60, m % 60)


def estimate_arrival_time(dep_time, from_code, to_code, connecting=False):
    """v0.19: estimated arrival hh:mm from a known dep time plus the
    great-circle duration. Returns '' when inputs are unknown or the math
    would be pure fiction (missing coords). Never written into arr_time:
    callers store it in arr_est so the UI can badge it as an estimate."""
    a = AIRPORT_COORDS.get((from_code or "").upper())
    b = AIRPORT_COORDS.get((to_code or "").upper())
    if not a or not b or not dep_time:
        return ""
    try:
        h, m = int(dep_time[:2]), int(dep_time[3:5])
    except (ValueError, IndexError):
        return ""
    hours = _haversine_km(a, b) / 750.0 + 0.7
    if connecting:
        hours += 2.5
    total = h * 60 + m + max(60, int(round(hours * 60 / 5.0)) * 5)
    total %= 24 * 60  # next-day arrival still renders as clock time
    return "{:02d}:{:02d}".format(total // 60, total % 60)


def airline_name(code):
    return AIRLINE_NAMES.get(code, code or "未知航司")


# Deals whose price itself is borrowed/interpolated: excluded from time
# coverage stats so the widget reflects real purchasable flights only.
NON_REAL_SOURCES = ("nearby-ref", "interp")


def time_coverage(deals):
    """Count dep/arr time quality across deals (pure, no IO).

    dep: exact (amadeus/airport-board + dep_time) / borrow (airport-board-x
    + dep_time) / missing. arr adds est (arr_est only, never real).
    NON_REAL_SOURCES rows are skipped: their price is already a reference.
    """
    cov = {"total": 0, "dep_exact": 0, "dep_borrow": 0, "dep_missing": 0,
           "arr_exact": 0, "arr_borrow": 0, "arr_est": 0, "arr_missing": 0}
    for d in deals:
        if (getattr(d, "source", "") or "") in NON_REAL_SOURCES:
            continue
        cov["total"] += 1
        dep_src = getattr(d, "dep_src", "") or getattr(d, "time_src", "")
        arr_src = getattr(d, "arr_src", "") or getattr(d, "time_src", "")
        if getattr(d, "dep_time", ""):
            cov["dep_borrow" if dep_src not in ("amadeus", "airport-board")
                else "dep_exact"] += 1
        else:
            cov["dep_missing"] += 1
        if getattr(d, "arr_time", ""):
            cov["arr_borrow" if arr_src not in ("amadeus", "airport-board")
                else "arr_exact"] += 1
        elif getattr(d, "arr_est", ""):
            cov["arr_est"] += 1
        else:
            cov["arr_missing"] += 1
    return cov


def booking_url(from_city, to_city, date):
    """Qunar H5 flight-list deep link (params match the SPA's own routing:
    depCity/arrCity/goDate + from=touch_index_search, verified against
    home.js searchFlight()). The legacy /h5/flight/oneway?fromCity=... URL
    was retired server-side and 302'd back to the flight home page."""
    q = urllib.parse.urlencode({
        "depCity": from_city,
        "arrCity": to_city,
        "goDate": date,
        "from": "touch_index_search",
    })
    return "https://m.flight.qunar.com/ncs/page/flightlist?" + q


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


def intl_booking_url(from_city, to_city, date):
    """Qunar H5 intl flight-list deep link (same routing family as the
    domestic list; the intl SPA pushes /ncs/page/interlist with the same
    depCity/arrCity/goDate query params)."""
    q = urllib.parse.urlencode({
        "depCity": from_city,
        "arrCity": to_city,
        "goDate": date,
        "from": "touch_index_search",
    })
    return "https://m.flight.qunar.com/ncs/page/interlist?" + q


def fetch_intl_promo_calendar(session, net_cfg, from_city, to_city,
                              date_from, date_to, tax_cfg):
    """Keyless international promo low-price calendar (qunar gateway).

    Same public gateway as the domestic calendar but with intl city names;
    returns only a few promo-priced dates per route (sparse but real RMB
    tax-included floors). Price is converted to a 'virtual bare price'
    (total - configured tax) to keep total_price() semantics consistent.
    """
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
        raise RuntimeError("qunar intl calendar bad response: " + str(j)[:200])
    from .alerts import tax_amount
    tax = tax_amount(tax_cfg)
    deals = []
    for e in j["data"].get("gflights") or []:
        d = e.get("date", "")
        p = e.get("price", "")
        code = e.get("code", "")
        if not d or not p or not (date_from <= d <= date_to):
            continue
        try:
            total = float(p)
        except (TypeError, ValueError):
            continue
        deals.append(FlightDeal(
            date=d,
            bare_price=round(total - tax, 1),
            flight_no=code,
            source="qunar-intl",
            url=intl_booking_url(from_city, to_city, d),
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
