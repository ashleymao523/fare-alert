# -*- coding: utf-8 -*-
"""12306 train fare source: leftTicketPrice query (no login, low frequency).

Seat classes are parsed generically: every *_price field 12306 returns becomes
a labeled option (二等座/一等座/商务座/硬卧/硬座/软卧/动卧/高级软卧...),
so whatever the API exposes shows up in the UI instead of being hard-coded.
Station cache keeps pinyin for autocomplete.
"""
import datetime as dt
import json
import os
import re
import time
from dataclasses import asdict

import requests

from .models import TrainFare

STATION_JS = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
PRICE_QUERY = "https://kyfw.12306.cn/otn/leftTicketPrice/query"

# price field prefix -> Chinese seat label (fields verified via tools/probe13.py)
SEAT_LABELS = {
    "swz": "商务座", "tz": "特等座", "zy": "一等座", "ze": "二等座",
    "gr": "高级软卧", "rw": "软卧", "srrb": "动卧", "errb": "一人软卧",
    "yrrb": "二人软卧", "yw": "硬卧", "yz": "硬座", "rz": "软座",
    "edsr": "二等卧(动)", "ydsr": "一等卧(动)", "edr": "二等卧(动)", "ydr": "一等卧(动)",
    "wz": "无座", "gg": "观光座", "tdrz": "特价软座", "yb": "包厢硬卧",
}
TRAIN_TYPE_KEEP = "GDCZTK"
STATION_CACHE_VERSION = 2
TRAIN_CACHE_VERSION = 2


def _headers(net_cfg):
    return {
        "User-Agent": net_cfg.get("user_agent_desktop", "Mozilla/5.0"),
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://kyfw.12306.cn/otn/leftTicketPrice/init",
    }


def _station_code(entry):
    if isinstance(entry, dict):
        return entry.get("code", "")
    return entry or ""


def get_stations(session, net_cfg, cache_path):
    """Return {station_name: {code, pinyin, py}}; cache 7 days."""
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            updated = dt.date.fromisoformat(data["updated"])
            fresh = dt.date.today() - updated < dt.timedelta(days=7)
            rich = data.get("v") == STATION_CACHE_VERSION
            if fresh and rich:
                return data["stations"]
        except Exception:
            pass
    r = session.get(STATION_JS, headers=_headers(net_cfg),
                    timeout=net_cfg.get("timeout_seconds", 25))
    r.raise_for_status()
    m = re.search(r"var station_names ='([^']+)'", r.text)
    if not m:
        raise RuntimeError("cannot parse station_name.js")
    stations = {}
    for ent in m.group(1).split("@"):
        if ent:
            parts = ent.split("|")
            stations[parts[1]] = {
                "code": parts[2],
                "pinyin": parts[3].lower(),
                "py": parts[4].lower(),
            }
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"v": STATION_CACHE_VERSION, "updated": str(dt.date.today()),
                   "stations": stations}, f, ensure_ascii=False)
    return stations


def parse_price(raw):
    """12306 price format: '05890' means 589.0 CNY."""
    if not raw or raw == "--":
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    return int(digits) / 10.0


def parse_seats(dto):
    seats = {}
    for k, v in dto.items():
        if not k.endswith("_price"):
            continue
        price = parse_price(v)
        if price is None:
            continue
        prefix = k[:-len("_price")]
        label = SEAT_LABELS.get(prefix.lower(), prefix.upper())
        seats[label] = price
    return seats


def query_pair(session, net_cfg, date, from_name, to_name, stations):
    if from_name not in stations or to_name not in stations:
        raise KeyError("station not found: " + from_name + "/" + to_name)
    params = {
        "leftTicketDTO.train_date": date,
        "leftTicketDTO.from_station": _station_code(stations[from_name]),
        "leftTicketDTO.to_station": _station_code(stations[to_name]),
        "purpose_codes": "ADULT",
    }
    r = session.get(PRICE_QUERY, params=params, headers=_headers(net_cfg),
                    timeout=net_cfg.get("timeout_seconds", 25))
    r.raise_for_status()
    items = r.json().get("data") or []
    fares = []
    seen = set()
    for it in items:
        d = it.get("queryLeftNewDTO") or {}
        code = d.get("station_train_code", "")
        if not code or code[0] not in TRAIN_TYPE_KEEP:
            continue
        key = code + "|" + d.get("start_time", "")
        if key in seen:
            continue
        seen.add(key)
        fares.append(TrainFare(
            pair=from_name + "-" + to_name,
            train_code=code,
            from_station=d.get("from_station_name", from_name),
            to_station=d.get("to_station_name", to_name),
            dep_time=d.get("start_time", ""),
            arr_time=d.get("arrive_time", ""),
            duration_text=d.get("lishi", ""),
            seats=parse_seats(d),
        ))
    return fares


def refresh_train_info(session, net_cfg, route_cfg, data_dir):
    """Query all configured station pairs, cache 24h in data/train_cache.json."""
    cache_file = os.path.join(data_dir, "train_cache.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, encoding="utf-8") as f:
                cached = json.load(f)
            age = dt.datetime.now() - dt.datetime.fromisoformat(cached["updated_at"])
            ok_age = age.total_seconds() < 24 * 3600
            ok_ver = cached.get("v") == TRAIN_CACHE_VERSION
            if ok_age and ok_ver and cached.get("route_id") == route_cfg["id"]:
                return cached
        except Exception:
            pass
    stations = get_stations(session, net_cfg, os.path.join(data_dir, "stations.json"))
    query_date = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    result = {
        "v": TRAIN_CACHE_VERSION,
        "route_id": route_cfg["id"],
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "query_date": query_date,
        "pairs": {},
    }
    tc = route_cfg.get("train_compare") or {}
    for pair in tc.get("station_pairs", []):
        key = "-".join(pair)
        try:
            fares = query_pair(session, net_cfg, query_date, pair[0], pair[1], stations)
            result["pairs"][key] = [asdict(f) for f in fares]
            time.sleep(1.5)
        except Exception as e:
            result["pairs"][key] = {"error": str(e)}
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return result
