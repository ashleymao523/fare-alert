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
from .alerts import conf_mark, dep_arr_text

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


def build_weekly(path, today=None, data_dir=None):
    """Build the weekly report dict from history.json.

    Returns {ok, period, routes:[{id, name, stats, text}], highlights, text}.
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
    doc["highlights"] = week_highlights(history)
    doc["sched_dows"] = _sched_dow_line(data_dir)
    doc["text"] = _summary_text(doc)
    doc["push_text"] = push_text(doc)
    return doc


def _fmt(v):
    n = round(float(v), 1)
    return str(int(n)) if n % 1 == 0 else str(n)


def _sched_dow_line(data_dir):
    '''v1.02: one line about board-library weekday coverage.
    Grey "borrowed time" flights trace back to weekdays the board
    API never deposited (Sunday historically). The weekly push now
    says which weekdays are still holes and when each self-heals -
    a run on day D deposits dow(D) AND dow(D+1), so a missing
    weekday heals on the next calendar date bearing it while the
    machine stays on.'''
    if not data_dir:
        return ""
    try:
        from core.sched_board import load_sched_db, sched_stats
        dows = sched_stats(load_sched_db(data_dir)).get("dows") or {}
    except Exception:
        return ""
    names = ["一", "二", "三", "四", "五", "六", "日"]
    miss = [i for i in range(7) if not int(dows.get(str(i), 0) or 0)]
    if not miss:
        return ""
    import datetime as _dt
    today = _dt.date.today()
    heal = []
    for i in miss:
        d = today
        for _ in range(7):
            d += _dt.timedelta(days=1)
            if d.weekday() == i:
                break
        heal.append("周{} {}自动补齐".format(names[i], d.strftime("%m/%d")))
    return "🛫 班期库已沉淀 {}/7 个星期（缺周{}）；常驻运行下 {}".format(
        7 - len(miss), "、".join(names[i] for i in miss), "、".join(heal[:2]))


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


def week_highlights(history, pct=15.0, abs_yuan=50.0):
    """v0.57: structured "worth watching this week" board, recomputed
    from the same archive as the route cards (every number derivable):

    biggest_drop    - largest week-over-week drop of the window minimum
    sharp_drops     - day-over-day drops inside the week clearing BOTH
                      gates (relative % AND absolute yuan, like /api/drops)
    below_threshold - routes whose latest snapshot has days below the line

    Pure; a calm week returns empty lists (the UI shows the calm text)."""
    days = sorted(history.get("days") or {})
    week_days = days[-WEEK_SIZE:]
    route_ids = []
    for day in week_days:
        for rid in (history["days"][day].get("routes") or {}):
            if rid not in route_ids:
                route_ids.append(rid)

    def _name(m):
        return "{}→{}".format(m.get("from_city", "?"), m.get("to_city", "?"))

    biggest = None
    for rid in route_ids:
        series = _series(history, rid)
        week = series[-WEEK_SIZE:]
        prev = series[-2 * WEEK_SIZE:-WEEK_SIZE]
        if not week or not prev:
            continue
        w = _stats_for(week)["min"]
        p = _stats_for(prev)["min"]
        if not p or w >= p:
            continue
        delta = round(w - p, 1)
        rel = round(delta * 100.0 / p, 1)
        cand = {"route_id": rid, "name": _name(week[-1][1]),
                "week_min": w, "prev_min": p, "delta": delta, "pct": rel}
        if biggest is None or delta < biggest["delta"]:
            biggest = cand

    sharps = []
    for d0, d1 in zip(week_days, week_days[1:]):
        r0 = history["days"][d0].get("routes") or {}
        r1 = history["days"][d1].get("routes") or {}
        for rid, m in r1.items():
            pm = r0.get(rid)
            t = m.get("cheapest_total")
            p = (pm or {}).get("cheapest_total")
            if not all(isinstance(x, (int, float)) and x > 0
                       for x in (t, p)):
                continue
            delta = round(float(t) - float(p), 1)
            rel = round(delta * 100.0 / float(p), 1)
            if delta < 0 and -rel >= float(pct) and -delta >= float(abs_yuan):
                s = {"route_id": rid, "name": _name(m),
                     "date": d1, "prev": round(float(p), 1),
                     "today": round(float(t), 1),
                     "delta": delta, "pct": rel}
                # v0.97: ride the best deal's schedule onto the drop row
                # (archived since v0.97 by core.history._route_metrics).
                for k in ("dep_time", "arr_time", "flight_no", "dur"):
                    if m.get(k):
                        s[k] = m[k]
                sharps.append(s)
    sharps.sort(key=lambda s: s["delta"])
    sharps = sharps[:5]

    below = []
    for rid in route_ids:
        series = _series(history, rid)
        if not series:
            continue
        day, m = series[-1]
        if m.get("days_below") and m.get("threshold"):
            b = {"route_id": rid, "name": _name(m),
                 "days_below": m.get("days_below"),
                 "threshold": m.get("threshold"),
                 "cheapest_total": m.get("cheapest_total"),
                 "best_date": m.get("best_date") or day}
            for k in ("dep_time", "arr_time", "flight_no", "dur"):
                if m.get(k):
                    b[k] = m[k]
            below.append(b)
    below.sort(key=lambda b: b.get("cheapest_total") or 1e18)

    return {"biggest_drop": biggest, "sharp_drops": sharps,
            "below_threshold": below,
            "text": _highlights_text(biggest, sharps, below, pct, abs_yuan)}


def _highlights_text(biggest, sharps, below, pct, abs_yuan):
    if not biggest and not sharps and not below:
        return "本周价格平稳：无破阈值路线、无骤降（双闸 {}%/¥{}）。".format(
            _fmt(pct), _fmt(abs_yuan))
    parts = []
    if biggest:
        parts.append("最大降幅 {} ¥{}→¥{}（{} / {}%）".format(
            biggest["name"], _fmt(biggest["prev_min"]),
            _fmt(biggest["week_min"]), _fmt(biggest["delta"]),
            _fmt(biggest["pct"])))
    if below:
        parts.append("{} 条路线当前低于阈值".format(len(below)))
    if sharps:
        s0 = sharps[0]
        when = str(s0.get("date") or "")[5:]
        if s0.get("dep_time"):
            when += " " + str(s0["dep_time"]) + "起飞"
        parts.append("本周 {} 次骤降，最大 {} ¥{}".format(
            len(sharps), when, _fmt(s0["today"])))
    return "⭐ 本周值得关注：" + "；".join(parts) + "。"


def push_text(report):
    """v0.58: the exact body a weekly push sends. The highlights line
    rides right under the head so the phone digest leads with what is
    worth watching; a calm week still gets its reassurance line.
    build_weekly.text stays the UI digest - this is the wire format."""
    body = (report or {}).get("text") or ""
    hl = (report or {}).get("highlights") or {}
    line = (hl.get("text") or "").strip()
    if not line or line in body:
        return body
    lines = body.split("\n")
    if lines and lines[0].startswith("📊"):
        head, rest = lines[0], "\n".join(lines[1:])
        return head + "\n" + line + ("\n" + rest if rest else "")
    return line + "\n" + body


def _summary_text(doc):
    if not doc.get("routes"):
        return "暂无历史数据，跑一次查询后每天自动归档指标；积累 8 天起周报带环比。"
    head = "📊 价格周报（{}）".format(doc.get("period") or "")
    body = "\n".join(r["text"] for r in doc["routes"])
    tail = (doc.get("sched_dows") or "").strip()
    return head + "\n" + body + ("\n" + tail if tail else "")


def global_best(snapshot):
    """v0.65: the single best buy across every route in a live
    snapshot. Min price/threshold ratio wins, lower price breaks
    ties - the same rule the v0.64 hero row applies client-side,
    now canonical server-side so pushes quote one answer. Deals
    without a numeric total or a positive threshold are ignored;
    returns None when nothing qualifies. Pure."""
    best = None
    for r in (snapshot or {}).get("routes") or []:
        try:
            th = float(r.get("threshold_total"))
        except (TypeError, ValueError):
            continue
        if th <= 0:
            continue
        for d in r.get("deals") or []:
            p = d.get("total_price")
            if not isinstance(p, (int, float)):
                continue
            key = (float(p) / th, float(p))
            if best is None or key < best[0]:
                best = (key, {
                    "route_id": r.get("id"),
                    "from_city": r.get("from_city", ""),
                    "to_city": r.get("to_city", ""),
                    "date": d.get("date") or "",
                    "price": float(p),
                    "dep_time": d.get("dep_time") or "",
                    "arr_time": d.get("arr_time") or "",
                    "time_src": d.get("time_src") or "",
                    "borrow_dow": d.get("borrow_dow") or "",
                    "borrow_votes": int(d.get("borrow_votes") or 0),
                    "borrow_unstable": bool(d.get("borrow_unstable")),
                    "threshold": th,
                    "savings": round(th - float(p), 2),
                })
    return best[1] if best else None


def global_best_line(gb):
    """One-line wire format: route, date, price, dep-arr times and
    the threshold gap. Over-threshold legs still get their line -
    '距心理价¥X' - so the push always names the front-runner."""
    if not gb:
        return ""
    date = (gb.get("date") or "")[5:]
    times = ""
    ta = dep_arr_text(gb)
    if ta:
        mk = conf_mark(gb)
        times = " ({0}{1})".format(ta, "·{0}".format(mk) if mk else "")
    route = "{0}→{1}".format(gb.get("from_city") or "?",
                             gb.get("to_city") or "?")
    sav = gb.get("savings") or 0
    tail = (" 比心理价低¥{0}".format(_fmt(sav)) if sav > 0
            else (" 距心理价¥{0}".format(_fmt(-sav)) if sav < 0 else ""))
    return "🏆 全局最优 {0} {1} ¥{2}{3}{4}".format(
        route, date, _fmt(gb.get("price")), times, tail).rstrip()


def attach_global_best(report, snapshot):
    """Merge the live global-best line into a weekly report's push
    text, right under the 📊 head (ahead of the highlights line -
    the unique answer leads). Pure: the caller loads the snapshot.
    No-op when nothing qualifies or the line is already in."""
    gb = global_best(snapshot)
    if not gb or not report:
        return report
    line = global_best_line(gb)
    body = report.get("push_text") or ""
    if not line or line in body:
        return report
    lines = body.split("\n")
    if lines and lines[0].startswith("📊"):
        rest = "\n".join(lines[1:])
        body = lines[0] + "\n" + line + ("\n" + rest if rest else "")
    else:
        body = line + "\n" + body
    report["push_text"] = body
    report["global_best"] = gb
    return report


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
