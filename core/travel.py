# -*- coding: utf-8 -*-
"""Keyless travel intel: destination weather (Open-Meteo) + FX (open.er-api).

Both are free public APIs with no registration - deliberately chosen so the
whole tool stays keyless unless the user opts into Amadeus.
"""
import json
import os
import time

import requests

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "travel_cache.json")

GEO_TTL = 30 * 86400
WEATHER_TTL = 3 * 3600
FX_TTL = 12 * 3600

# WMO weather interpretation codes -> (emoji, zh label)
WMO = {
    0: ("☀️", "晴"), 1: ("🌤️", "大部晴"), 2: ("⛅", "多云"), 3: ("☁️", "阴"),
    45: ("🌫️", "雾"), 48: ("🌫️", "雾凇"),
    51: ("🌦️", "小毛雨"), 53: ("🌦️", "毛毛雨"), 55: ("🌧️", "密毛雨"),
    56: ("🌧️", "冻毛雨"), 57: ("🌧️", "强冻雨"),
    61: ("🌦️", "小雨"), 63: ("🌧️", "中雨"), 65: ("🌧️", "大雨"),
    66: ("🌧️", "冻雨"), 67: ("🌧️", "强冻雨"),
    71: ("🌨️", "小雪"), 73: ("❄️", "中雪"), 75: ("❄️", "大雪"), 77: ("🌨️", "雪粒"),
    80: ("🌦️", "阵雨"), 81: ("🌧️", "强阵雨"), 82: ("⛈️", "暴雨"),
    85: ("🌨️", "阵雪"), 86: ("❄️", "强阵雪"),
    95: ("⛈️", "雷暴"), 96: ("⛈️", "雷雹"), 99: ("⛈️", "强雷雹"),
}

# destination city -> local currency for the FX strip (intl routes only)
CURRENCY_BY_CITY = {
    "曼谷": "THB", "普吉": "THB", "清迈": "THB", "甲米": "THB", "苏梅": "THB",
    "东京": "JPY", "大阪": "JPY", "札幌": "JPY", "名古屋": "JPY", "福冈": "JPY", "冲绳": "JPY",
    "首尔": "KRW", "釜山": "KRW", "济州": "KRW",
    "新加坡": "SGD", "吉隆坡": "MYR", "槟城": "MYR", "沙巴": "MYR",
    "香港": "HKD", "澳门": "MOP", "台北": "TWD", "高雄": "TWD",
    "马尼拉": "PHP", "宿务": "PHP", "长滩": "PHP",
    "河内": "VND", "岘港": "VND", "胡志明": "VND", "芽庄": "VND",
    "巴厘岛": "IDR", "雅加达": "IDR",
    "迪拜": "AED", "阿布扎比": "AED", "多哈": "QAR", "伊斯坦布尔": "TRY",
    "莫斯科": "RUB", "伦敦": "GBP", "巴黎": "EUR", "罗马": "EUR", "柏林": "EUR",
    "阿姆斯特丹": "EUR", "维也纳": "EUR", "苏黎世": "CHF", "马德里": "EUR",
    "巴塞罗那": "EUR", "米兰": "EUR", "慕尼黑": "EUR",
    "哥本哈根": "DKK", "斯德哥尔摩": "SEK", "赫尔辛基": "EUR", "奥斯陆": "NOK",
    "纽约": "USD", "洛杉矶": "USD", "旧金山": "USD", "夏威夷": "USD",
    "悉尼": "AUD", "墨尔本": "AUD", "布里斯班": "AUD", "奥克兰": "NZD",
    "新德里": "INR", "孟买": "INR", "开罗": "EGP", "内罗毕": "KES",
    "开普敦": "ZAR", "约翰内斯堡": "ZAR", "毛里求斯": "MUR", "塞舌尔": "SCR",
}


def _load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(c):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False)
    except Exception:
        pass


def _get(c, key, ttl, fetch):
    now = time.time()
    ent = c.get(key)
    if ent and now - float(ent.get("ts", 0)) < ttl:
        return ent.get("v")
    try:
        v = fetch()
        c[key] = {"ts": now, "v": v}
        return v
    except Exception:
        # stale is better than nothing
        return ent.get("v") if ent else None
    finally:
        _save_cache(c)


def geocode(session, city, net_cfg):
    def f():
        r = session.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh"},
            timeout=net_cfg.get("timeout_seconds", 20))
        r.raise_for_status()
        res = (r.json().get("results") or [None])[0]
        if not res:
            raise RuntimeError("geo miss: " + city)
        return {"lat": res["latitude"], "lon": res["longitude"],
                "tz": res.get("timezone", "auto")}
    return _get(_load_cache(), "geo:" + city, GEO_TTL, f)


def dest_weather(session, city, net_cfg, days=7):
    """7-day destination forecast. Returns None when both geo & fetch fail."""
    c = _load_cache()
    g = _get(c, "geo:" + city, GEO_TTL,
             lambda: geocode(session, city, net_cfg))
    if not g:
        return None

    def wf():
        r = session.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": g["lat"], "longitude": g["lon"],
                    "daily": "temperature_2m_max,temperature_2m_min,"
                             "weather_code,precipitation_probability_max",
                    "timezone": g.get("tz") or "auto",
                    "forecast_days": days},
            timeout=net_cfg.get("timeout_seconds", 20))
        r.raise_for_status()
        d = r.json().get("daily") or {}
        out = []
        for i, ds in enumerate(d.get("time") or []):
            code = int((d.get("weather_code") or [0] * (i + 1))[i] or 0)
            icon, label = WMO.get(code, ("🌡️", "未知"))
            out.append({
                "date": ds,
                "hi": round((d.get("temperature_2m_max") or [0] * (i + 1))[i]),
                "lo": round((d.get("temperature_2m_min") or [0] * (i + 1))[i]),
                "pop": (d.get("precipitation_probability_max") or [None] * (i + 1))[i],
                "icon": icon, "label": label,
            })
        return out
    return _get(c, "wx:" + city, WEATHER_TTL, wf)


def cny_rate(session, currency, net_cfg):
    """1 CNY = ? <currency>. Returns None when unsupported/unreachable."""
    if not currency or currency == "CNY":
        return None

    def f():
        r = session.get("https://open.er-api.com/v6/latest/CNY",
                        timeout=net_cfg.get("timeout_seconds", 20))
        r.raise_for_status()
        j = r.json()
        if j.get("result") != "success":
            raise RuntimeError("fx bad response")
        return j.get("rates") or {}
    rates = _get(_load_cache(), "fx:CNY", FX_TTL, f)
    if not rates:
        return None
    v = rates.get(currency)
    if v is None:
        return None
    return {"currency": currency, "rate": round(v, 4),
            "per_1000": round(v * 1000, 1)}

