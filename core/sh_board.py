# -*- coding: utf-8 -*-
"""上海机场(集团)官网航班板 -> 精确起降时刻(零密钥).

数据源: shanghaiairport.com 航班信息页(/flights)使用的公开只读接口,
与浏览器访问完全同源(无签名/无登录/无频控挑战):
  POST /AvinexApi/OldFlightHandler.aspx  action=GetData
    direction=1 出发板(上海起飞) / 2 到达板(上海落地)
    flightNum=HO1254 按航班号直查
    timeDays=-1|0|1  昨/今/明日(实测 >=2 返回空)
  返回行含 计划出发时间/计划到达时间/出发地/目的地(城市+机场)/
  航空公司/候机楼/IATA 代码, 是机场官方发布的当日计划时刻.

v1.18 用途(公务舱时刻精度阶梯的第 2 级):
  1) 窗口内精确: obs 日期是今/明 -> 该日期的官方计划起降直接回写
     (实测同一航班相邻日期到达时刻可差 5 分钟, 按星期借用只能作
      第 3 级兜底);
  2) 星期沉淀: 每次查询的行同时并入 flight_sched_db.json 的
     fno+星期桶, 远期日期由 v1.16 借用契约消费(标『借用』).

红线: 只读查询 / 低频(每 fno+方向+偏移 6h 缓存, 全局每日 24 次
硬上限, 与萧山板共用 board_fetch_log.json 记账) / 公开数据无 PII.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import time
import urllib.parse

from .sched_board import DB_NAME, _atomic_write

BOARD_URL = ("https://www.shanghaiairport.com/AvinexApi/"
             "OldFlightHandler.aspx")
BOARD_REFERER = "https://www.shanghaiairport.com/flights/index.html"
SH_TTL = 6 * 3600
SH_DAILY_MAX = 24
SH_LOG_KIND = "sh_board"
SH_LOG_NAME = "board_fetch_log.json"  # shared ledger with the HGH board
METRO_KEY = "上海"


def _norm_no(s):
    return "".join((s or "").split()).upper()


def _city(field):
    """'北京 大兴' -> '北京'; list/empty safe."""
    if not field or isinstance(field, (list, tuple)):
        return ""
    return str(field).split()[0].strip() if str(field).split() else ""


def _hm(ts):
    """'2026-09-16 21:25:00' -> '21:25'."""
    s = str(ts or "").strip()
    return s[11:16] if len(s) >= 16 else ""


def _day(ts):
    s = str(ts or "").strip()[:10]
    try:
        return _dt.date.fromisoformat(s)
    except ValueError:
        return None


def _log_count(data_dir, today):
    try:
        with open(os.path.join(data_dir, SH_LOG_NAME),
                  encoding="utf-8") as f:
            log = json.load(f)
        return int((log.get(SH_LOG_KIND) or {}).get(today, 0))
    except Exception:
        return 0


def _bump_log(data_dir, today):
    path = os.path.join(data_dir, SH_LOG_NAME)
    log = {}
    try:
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    except Exception:
        pass
    days = log.setdefault(SH_LOG_KIND, {})
    days[today] = int(days.get(today, 0)) + 1
    cutoff = (_dt.date.today() - _dt.timedelta(days=3)).isoformat()
    for k in list(log):
        log[k] = {d: n for d, n in log[k].items() if d >= cutoff}
    try:
        os.makedirs(data_dir, exist_ok=True)
        _atomic_write(path, log)
    except Exception:
        pass


def _normalize(raw):
    """One board row -> {fno, dep, arr, date, from, to, airline,
    terminal, src} or None when the flight number is missing."""
    fno = _norm_no(raw.get("主航班号"))
    if not fno:
        return None
    return {
        "fno": fno,
        "dep": _hm(raw.get("计划出发时间")),
        "arr": _hm(raw.get("计划到达时间")),
        "date": str(raw.get("计划出发时间") or "")[:10],
        "from": _city(raw.get("出发地")),
        "to": _city(raw.get("目的地")),
        "airline": str(raw.get("航空公司") or ""),
        "terminal": str(raw.get("候机楼") or ""),
        "src": "shanghai-board",
    }


def fetch_flight(session, net_cfg, fno, direction, day_offset,
                 data_dir, force=False):
    """Query one flight number on the Shanghai board.

    direction: 1 departures / 2 arrivals; day_offset -1|0|1.
    6h per-key cache + a global daily network cap keep the cadence
    inside the AGENTS.md red lines. Returns (rows, how) with how in
    ('net', 'cache', 'capped') - a capped call is a no-op, not an
    error, so the patrol round stays quiet."""
    fno = _norm_no(fno)
    today = _dt.date.today().isoformat()
    path = os.path.join(
        data_dir, "board_sh_{f}_{d}_{o}.json".format(
            f=fno, d=int(direction), o=int(day_offset)))
    if not force and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                ent = json.load(f)
            if time.time() - float(ent.get("ts", 0)) < SH_TTL:
                return ent.get("rows", []), "cache"
        except Exception:
            pass
    if not force and _log_count(data_dir, today) >= SH_DAILY_MAX:
        return [], "capped"
    form = urllib.parse.urlencode({
        "action": "GetData", "currentPage": 1, "pageSize": 20,
        "flightType": 1, "direction": int(direction),
        "airCities": "", "airCities2": "", "airCompanies": "",
        "timeDays": int(day_offset), "timeSpan": "00:00-23:59",
        "flightNum": fno,
    }).encode()
    try:
        r = session.post(BOARD_URL, data=form, headers={
            "User-Agent": net_cfg.get(
                "user_agent_mobile", "Mozilla/5.0"),
            "Referer": BOARD_REFERER,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            # WAF contract (verified 2026-09-17): a bytes body without
            # an explicit Content-Type gets a 403 challenge page; the
            # endpoint also mislabels its JSON as text/html.
            "Content-Type":
                "application/x-www-form-urlencoded; charset=UTF-8",
        }, timeout=net_cfg.get("timeout_seconds", 25))
        r.raise_for_status()
        try:
            j = r.json()
        except ValueError:  # server mislabels JSON as text/html
            j = json.loads(r.text)
        if not j.get("success"):
            raise RuntimeError("sh board bad flag")
        raw = json.loads(
            ((j.get("data") or {}).get("flightList")) or "[]")
    except Exception:
        _bump_log(data_dir, today)  # failed tries burn budget too
        raise
    rows = [x for x in (_normalize(rr) for rr in raw) if x]
    os.makedirs(data_dir, exist_ok=True)
    _atomic_write(path, {"ts": time.time(), "rows": rows})
    _bump_log(data_dir, today)
    return rows, "net"


def merge_sh_rows(db, rows):
    """File Shanghai-board rows into the shared sched db (own-dow,
    richer-wins, HGH airport-board rows stay authoritative)."""
    changed = False
    for r in rows or []:
        if not (r.get("dep") and r.get("arr")):
            continue
        d = _day(r.get("date"))
        if d is None:
            continue
        dow = str(d.weekday())
        fdb = db.setdefault("flights", {}).setdefault(
            r["fno"], {"dows": {}})
        ent = {"dep": r["dep"], "arr": r["arr"],
               "from": r.get("from", ""), "to": r.get("to", ""),
               "airline": r.get("airline", ""), "src": "shanghai-board"}
        cur = fdb["dows"].get(dow)
        if cur is None:
            fdb["dows"][dow] = ent
            changed = True
        elif cur.get("src") == "airport-board":
            # HGH real board observation outranks the metro partner
            for k in ("dep", "arr", "from", "to"):
                if not cur.get(k) and ent.get(k):
                    cur[k] = ent[k]
                    changed = True
        elif any(cur.get(k) != ent.get(k)
                 for k in ("dep", "arr", "from", "to")):
            # same-tier refresh: per-date plan times can shift, the
            # newest official row wins
            fdb["dows"][dow] = ent
            changed = True
    return changed


def _is_sh_leg(from_city, to_city):
    return (METRO_KEY in str(from_city or "")
            or METRO_KEY in str(to_city or ""))


def exact_targets(history, today=None, horizon=2):
    """Timeless obs rows whose fare date is inside the board window
    (today..today+horizon) on Shanghai legs. Pure."""
    today = today or _dt.date.today()
    out = []
    for rid, r in (history.get("routes") or {}).items():
        fc, tc = r.get("from_city", ""), r.get("to_city", "")
        if not _is_sh_leg(fc, tc):
            continue
        for o in r.get("obs") or []:
            if not (o.get("fno") or ""):
                continue
            if (o.get("dep") or "") and (o.get("arr") or ""):
                continue
            d = _day(o.get("date"))
            if d is None or not (today <= d <= today + _dt.timedelta(
                    days=horizon)):
                continue
            out.append({
                "route_id": rid, "date": o["date"], "fno": o["fno"],
                "from_city": fc, "to_city": tc,
                "direction": 2 if METRO_KEY in str(tc) else 1,
            })
    return out


def dow_targets(history, sched_db, max_fnos=4):
    """Distinct timeless fnos on Shanghai legs whose needed weekdays
    are still missing from the sched db - once every needed dow is
    deposited, the fno stops querying (queries self-extinguish)."""
    need = {}
    for rid, r in (history.get("routes") or {}).items():
        fc, tc = r.get("from_city", ""), r.get("to_city", "")
        if not _is_sh_leg(fc, tc):
            continue
        for o in r.get("obs") or []:
            fno = _norm_no(o.get("fno"))
            if not fno or ((o.get("dep") or "") and (o.get("arr") or "")):
                continue
            d = _day(o.get("date"))
            if d is None:
                continue
            key = (fno, 2 if METRO_KEY in str(tc) else 1)
            need.setdefault(key, set()).add(str(d.weekday()))
    flights = (sched_db or {}).get("flights") or {}
    out = []
    for (fno, direction), dows in sorted(need.items()):
        have = ((flights.get(fno) or {}).get("dows") or {})
        if any(not (have.get(dw) or {}).get("dep")
               and not (have.get(dw) or {}).get("arr")
               for dw in dows):
            out.append({"fno": fno, "direction": direction,
                        "dows": sorted(dows)})
        if len(out) >= max_fnos:
            break
    return out


def apply_exact_times(history, rows, now=None):
    """Write official in-window times onto matching timeless obs
    (route cities must match the row's cities). In-place; returns
    the number of upgraded observations."""
    now = now or _dt.datetime.now().strftime("%Y-%m-%dT%H:%M")
    idx = {}
    for rid, r in (history.get("routes") or {}).items():
        for o in r.get("obs") or []:
            key = (str(o.get("date") or ""), _norm_no(o.get("fno")))
            if key[0] and key[1]:
                idx.setdefault(key, []).append((r, o))
    n = 0
    for row in rows or []:
        for r, o in idx.get((row.get("date", ""),
                             _norm_no(row.get("fno"))), []):
            if (o.get("dep") or "") and (o.get("arr") or ""):
                continue
            if row.get("from") and row["from"] != (r.get("from_city")
                                                   or ""):
                continue
            if row.get("to") and row["to"] != (r.get("to_city")
                                               or ""):
                continue
            o["dep"] = row["dep"]
            o["arr"] = row["arr"]
            o["ts"] = now
            o["tsrc"] = "shanghai-board"
            n += 1
    return n


def sh_fill(session, net_cfg, data_dir, history, log=None,
            max_fnos=4):
    """Driver: exact-date fills for in-window rows + dow deposits
    for the rest. Bounded per run (max_fnos x 2 offsets), globally
    daily-capped; returns stats for the patrol card."""
    from .sched_board import load_sched_db
    # Shanghai WAF rate-limits rapid-fire POSTs (verified: 8 calls at
    # ~0.1s spacing all got 403, 3s spacing all passed) - pace the
    # driver the same way the booking paths do, and stop early when
    # the WAF keeps answering 403 (a dirty IP cools down; hammering
    # only extends the block). Tests inject sh_pace=0.
    pace = net_cfg.get("sh_pace")
    if pace is None:
        pace = max(2.0, float(net_cfg.get("call_interval") or 2.5))
    stats = {"queries": 0, "exact": 0, "dow_new": 0,
             "fnos": 0, "capped": False}
    today = _dt.date.today()
    sched_path = os.path.join(data_dir, DB_NAME)
    try:
        with open(sched_path, encoding="utf-8") as f:
            db = json.load(f)
    except Exception:
        db = {"fmt": 2, "updated": 0, "flights": {}}
    # priority 1: rows whose date the board can answer exactly
    ex = exact_targets(history, today)
    plan = []
    seen = set()
    for t in ex:
        k = (t["fno"], t["direction"])
        if k not in seen:
            seen.add(k)
            plan.append({"fno": t["fno"], "direction": t["direction"]})
    # priority 2: fnos still missing dow deposits
    for t in dow_targets(history, db, max_fnos=max_fnos):
        k = (t["fno"], t["direction"])
        if k not in seen:
            seen.add(k)
            plan.append({"fno": t["fno"], "direction": t["direction"]})
    plan = plan[:max_fnos]
    changed = False
    first_net = True
    fails = 0
    for p in plan:
        stop = False
        for off in (0, 1):
            if not first_net:
                time.sleep(pace)
            try:
                rows, how = fetch_flight(
                    session, net_cfg, p["fno"], p["direction"],
                    off, data_dir)
            except Exception as e:
                first_net = False
                fails += 1
                if log:
                    log.warning("sh board %s off%d failed: %s"
                                % (p["fno"], off, e))
                if fails >= 2:
                    stats["breaker"] = True
                    stop = True
                    break
                continue
            first_net = False
            fails = 0
            if how == "capped":
                stats["capped"] = True
                stop = True
                break
            if how == "net":
                stats["queries"] += 1
            if rows:
                stats["exact"] += apply_exact_times(history, rows)
                changed = merge_sh_rows(db, rows) or changed
        if stop:
            break
        stats["fnos"] += 1
    if changed:
        db["updated"] = time.time()
        try:
            os.makedirs(data_dir, exist_ok=True)
            _atomic_write(sched_path, db)
            if log:
                log.info("sh board deposited dow rows into sched db")
        except Exception as e:
            if log:
                log.warning("sh board sched db write failed: %s" % e)
    return stats
