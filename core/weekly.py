# -*- coding: utf-8 -*-
"""Weekly insight report (M4): stats recomputable from history.json.

"This week" = the latest 7 archived days per route (data-driven, polling
gaps tolerated); "last week" = the 7 days before that. The Chinese text is
template-generated so every number in it can be recomputed and asserted.
"""
import datetime as dt
import json
import os
import time

from .history import load_history

WEEK_SIZE = 7
PUSH_INTERVAL = 7 * 86400  # seconds between weekly pushes
RETRY_BACKOFF = 6 * 3600  # wait before retrying a failed weekly push


def _series(history, route_id):
    """[(date, metrics)] sorted by date for one route."""
    out = []
    for day in sorted(history.get("days", {})):
        m = (history["days"][day].get("routes") or {}).get(route_id)
        if m and isinstance(m.get("cheapest_total"), (int, float)):
            out.append((day, m))
    return out


def _stats_for(seg):
    """min / avg / best_date over [(date, metrics)]."""
    vals = [float(m["cheapest_total"]) for _, m in seg]
    best_day, best_m = min(seg, key=lambda x: x[1]["cheapest_total"])
    return {
        "min": round(min(vals), 1),
        "avg": round(sum(vals) / len(vals), 1),
        "best_date": best_m.get("best_date") or best_day,
        "seen_date": best_day,
    }


def build_weekly(path, today=None):
    """Build the weekly report dict from history.json.

    Returns {ok, period, routes:[{id, name, stats, text}], text}.
    Every number in text comes from stats (recomputable, DoD G4)."""
    history = load_history(path)
    all_days = sorted(history.get("days", {}))
    route_ids = []
    for day in all_days:
        for rid in (history["days"][day].get("routes") or {}):
            if rid not in route_ids:
                route_ids.append(rid)
    routes_out = []
    for rid in route_ids:
        series = _series(history, rid)
        if len(series) < 1:
            continue
        week = series[-WEEK_SIZE:]
        prev = series[-2 * WEEK_SIZE:-WEEK_SIZE]
        w = _stats_for(week)
        latest = week[-1][1]
        name = "{}→{}".format(latest.get("from_city", "?"),
                             latest.get("to_city", "?"))
        r = {
            "id": rid,
            "name": name,
            "week": w,
            "days_seen": len(week),
            "prev": _stats_for(prev) if prev else None,
            "latest": {
                "cheapest_total": latest.get("cheapest_total"),
                "days_below": latest.get("days_below"),
                "threshold": latest.get("threshold"),
                "best_date": latest.get("best_date"),
            },
            "series": [[d, m["cheapest_total"]] for d, m in week],
        }
        r["text"] = _route_text(r)
        routes_out.append(r)
    period = ""
    if all_days:
        first = all_days[-min(WEEK_SIZE, len(all_days))][5:]
        period = "{}~{}".format(first, all_days[-1][5:])
    doc = {
        "ok": bool(routes_out),
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "period": period,
        "routes": routes_out,
    }
    doc["text"] = _summary_text(doc)
    return doc


def _fmt(v):
    n = round(float(v), 1)
    return str(int(n)) if n % 1 == 0 else str(n)


def _route_text(r):
    w = r["week"]
    latest = r["latest"]
    lines = ["{}：本周最低含税价 ¥{}（{} 出发），本周均价 ¥{}".format(
        r["name"], _fmt(w["min"]), str(w["best_date"]), _fmt(w["avg"]))]
    p = r.get("prev")
    if p:
        delta = round(w["min"] - p["min"], 1)
        pct = ("{}%".format(_fmt(round(-delta / p["min"] * 100, 1)))
               if p["min"] else "")
        if delta < 0:
            lines[-1] += "，比上周最低 ¥{} 便宜 ¥{}{}".format(
                _fmt(p["min"]), _fmt(-delta),
                "（" + pct + "）" if pct else "")
        elif delta > 0:
            lines[-1] += "，比上周最低 ¥{} 贵 ¥{}{}".format(
                _fmt(p["min"]), _fmt(delta),
                "（" + pct + "）" if pct else "")
        else:
            lines[-1] += "，与上周最低持平"
    else:
        lines[-1] += "（上周暂无数据）"
    if latest.get("threshold"):
        lines.append("当前窗口内 {} 天低于阈值 ¥{}".format(
            latest.get("days_below", 0), _fmt(latest["threshold"])))
    return "；".join(lines) + "。"


def _summary_text(doc):
    if not doc.get("routes"):
        return "暂无历史数据，跑一次查询后每天自动归档指标；积累 8 天起周报带环比。"
    head = "📊 价格周报（{}）".format(doc.get("period") or "")
    body = "\n".join(r["text"] for r in doc["routes"])
    return head + "\n" + body


def should_push(cfg, path):
    """Weekly push fires only when enabled AND >=7d since last push.
    A recent failure backs off (no push storm every loop cycle)."""
    if not (cfg.get("push") or {}).get("weekly_enabled", False):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        doc = {}
    last = float(doc.get("ts", 0) or 0)
    retry_after = float(doc.get("retry_after", 0) or 0)
    if retry_after and time.time() < retry_after:
        return False  # failed recently: back off
    return (time.time() - last) >= PUSH_INTERVAL


def mark_pushed(path):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time()}, f)
    except Exception:
        raise


def mark_failed(path, retry_secs=RETRY_BACKOFF):
    """Record a failed weekly push: keep the 7d timer, retry after backoff."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"retry_after": time.time() + retry_secs}, f)
    except Exception:
        raise
