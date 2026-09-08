# -*- coding: utf-8 -*-
"""12306 train fare source: leftTicketPrice query (no login, low frequency)."""
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


def _headers(net_cfg):
    return {
        "User-Agent": net_cfg.get("user_agent_desktop", "Mozilla/5.0"),
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://kyfw.12306.cn/otn/leftTicketPrice/init",
    }


def get_stations(session, net_cfg, cache_path):
    if os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
            updated = dt.date.fromisoformat(data["updated"])
            if dt.date.today() - updated < dt.timedelta(days=7):
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
            stations[parts[1]] = parts[2]
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({"updated": str(dt.date.today()), "stations": stations},
                  f, ensure_ascii=False)
    return stations


def parse_price(raw):
    """12306 price format: '05890' means 589.0 CNY."""
    if not raw or raw == "--":
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    return int(digits) / 10.0


def query_pair(session, net_cfg, date, from_name, to_name, stations):
    if from_name not in stations or to_name not in stations:
        raise KeyError("station not found: " + from_name + "/" + to_name)
    params = {
        "leftTicketDTO.train_date": date,
        "leftTicketDTO.from_station": stations[from_name],
        "leftTicketDTO.to_station": stations[to_name],
        "purpose_codes": "ADULT",
    }
    r = session.get(PRICE_QUERY, params=params, headers=_headers(net_cfg),
                    timeout=net_cfg.get("timeout_seconds", 25))
    r.raise_for_status()
    items = r.json().get("data") or []
    fares = []
    for it in items:
        d = it.get("queryLeftNewDTO") or {}
        code = d.get("station_train_code", "")
        if not code or code[0] not in "GDC":
            continue
        fares.append(TrainFare(
            pair=from_name + "-" + to_name,
            train_code=code,
            from_station=d.get("from_station_name", from_name),
            to_station=d.get("to_station_name", to_name),
            dep_time=d.get("start_time", ""),
            arr_time=d.get("arrive_time", ""),
            duration_text=d.get("lishi", ""),
            second_class=parse_price(d.get("ze_price")),
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
            if age.total_seconds() < 24 * 3600 and cached.get("route_id") == route_cfg["id"]:
                return cached
        except Exception:
            pass
    stations = get_stations(session, net_cfg, os.path.join(data_dir, "stations.json"))
    query_date = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    result = {
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
