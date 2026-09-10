# -*- coding: utf-8 -*-
"""机场公开班期板 -> 周班期参考时刻库(零密钥).

数据源: 萧山机场官网「航班信息」页使用的公开只读接口(与浏览器访问同源):
  /api/leave_import/hbh/   当日出发班期板: 每航班含计划起飞时间 jhsj
  /api/arrive_import/hbh/  当日到达班期板: 含计划到达 jhsj 与前站计划起飞 preschtime

原理: 航班时刻按航季排班, 同一航班号在同一星期几的时刻高度稳定.
每日低频抓取当日板(6h 缓存, 每块板每日至多 2 次真实请求, 成败均计数), 按航班号+星期几沉淀成
参考时刻库, 逐步覆盖 60 天日历里各航班的计划起降时刻.

红线: 只读 GET / 低频(6h TTL) / 公开数据无 PII / 不参与提醒触发条件.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import time

BOARD_BASE = "https://apisys.h22.66571.com/api"
BOARD_TTL = 6 * 3600
DAILY_MAX = 2  # hard per-board daily fetch cap (AGENTS.md red line)
DB_NAME = "flight_sched_db.json"
LOG_NAME = "board_fetch_log.json"
REFERER = "https://www.hzairport.com/flight/index.html"


def _norm_no(s):
    return "".join((s or "").split()).upper()


def _city(field):
    """'重庆/江北' -> '重庆'; 列表/空安全."""
    if not field or isinstance(field, (list, tuple)):
        return ""
    return str(field).split("/")[0].strip()


def _hhmm(ts):
    try:
        return str(ts)[11:16]
    except Exception:
        return ""


def _atomic_write(path, obj):
    """tmp + os.replace: readers never observe a half-written file."""
    tmp = "%s.%d.tmp" % (path, os.getpid())  # pid suffix: no cross-process clash
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


_HGH_KEYS = ("杭州", "hangzhou", "hgh", "xiaoshan")


def touches_hangzhou(routes):
    """True when any route endpoint mentions Hangzhou (config keys from_city/to_city)."""
    for r in routes or []:
        blob = (str(r.get("from_city") or r.get("from") or "")
                + " " + str(r.get("to_city") or r.get("to") or "")).lower()
        if any(k in blob for k in _HGH_KEYS):
            return True
    return False


def _daily_count(data_dir, kind, today):
    try:
        with open(os.path.join(data_dir, LOG_NAME), encoding="utf-8") as f:
            log = json.load(f)
        return int((log.get(kind) or {}).get(today, 0))
    except Exception:
        return 0


def _bump_daily(data_dir, kind, today):
    path = os.path.join(data_dir, LOG_NAME)
    log = {}
    try:
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    except Exception:
        pass
    days = log.setdefault(kind, {})
    days[today] = int(days.get(today, 0)) + 1
    cutoff = (_dt.date.today() - _dt.timedelta(days=3)).isoformat()
    for k in list(log):
        log[k] = {d: n for d, n in log[k].items() if d >= cutoff}
    try:
        os.makedirs(data_dir, exist_ok=True)
        _atomic_write(path, log)
    except Exception:
        pass


def _cleanup_board_cache(data_dir, keep_days=7):
    try:
        cutoff = time.time() - keep_days * 86400
        for fn in os.listdir(data_dir):
            if fn.startswith("board_") and fn.endswith(".json"):
                p = os.path.join(data_dir, fn)
                if os.path.getmtime(p) < cutoff:
                    os.remove(p)
    except Exception:
        pass


def fetch_board(session, net_cfg, kind, data_dir, force=False):
    """抓当日班期板(leave|arrive), 落盘缓存 BOARD_TTL. 返回 (rows, cached)."""
    today = _dt.date.today().isoformat()
    path = os.path.join(data_dir, "board_%s_%s.json" % (kind, today))
    now = time.time()
    if not force and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                ent = json.load(f)
            if now - float(ent.get("ts", 0)) < BOARD_TTL:
                return ent.get("rows", []), True
        except Exception:
            pass
    if not force and _daily_count(data_dir, kind, today) >= DAILY_MAX:
        # hard cap: serve the stale cache instead of a 3rd request
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    ent = json.load(f)
                return ent.get("rows", []), True
            except Exception:
                pass
        raise RuntimeError("daily fetch cap reached for board " + kind)
    url = "%s/%s_import/hbh/" % (BOARD_BASE, kind)
    try:
        r = session.get(url, headers={
            "User-Agent": net_cfg.get("user_agent_mobile", "Mozilla/5.0"),
            "Referer": REFERER,
            "Accept": "application/json",
        }, timeout=net_cfg.get("timeout_seconds", 25))
        r.raise_for_status()
        j = r.json()
        if j.get("flag") != 1:
            raise RuntimeError("board api bad flag: " + str(j.get("msg"))[:80])
        rows = j.get("data") or []
    except Exception:
        # failed attempts burn the daily budget too (no 45min retry storm)
        _bump_daily(data_dir, kind, today)
        raise
    os.makedirs(data_dir, exist_ok=True)
    _atomic_write(path, {"ts": now, "rows": rows})
    _bump_daily(data_dir, kind, today)
    return rows, False


def _entry_from_leave(row):
    no = _norm_no(row.get("hbh"))
    if not no:
        return None
    return {
        "dep": _hhmm(row.get("jhsj")),
        "arr": "",
        "from": _city(row.get("chinese_sfcs")),
        "to": _city(row.get("chinese_mdcs")),
        "airline": row.get("chinese_hs") or "",
        "craft": row.get("jxzs") or "",
        "src": "airport-board",
    }


def _entry_from_arrive(row):
    no = _norm_no(row.get("hbh"))
    if not no:
        return None
    return {
        "dep": _hhmm(row.get("preschtime")),
        "arr": _hhmm(row.get("jhsj")),
        "from": _city(row.get("chinese_sfcs")),
        "to": _city(row.get("chinese_mdcs")),
        "airline": row.get("chinese_hs") or "",
        "craft": row.get("jxzs") or "",
        "src": "airport-board",
    }


def update_sched_db(session, net_cfg, data_dir, log=None):
    """抓两个板并合并进持久时刻库. 返回更新后的库 dict."""
    db_path = os.path.join(data_dir, DB_NAME)
    db = {"updated": 0, "flights": {}}
    try:
        with open(db_path, encoding="utf-8") as f:
            db = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        # never wipe a (possibly half-written) db: back it up, rebuild
        try:
            os.replace(db_path, "%s.corrupt-%d" % (db_path, int(time.time())))
        except Exception:
            pass
        if log:
            log.warning("sched db unreadable, backed up + rebuilding: %s" % e)
        pass
    today = _dt.date.today()
    dow = str(today.weekday())
    changed = False
    for kind, conv in (("leave", _entry_from_leave), ("arrive", _entry_from_arrive)):
        try:
            rows, cached = fetch_board(session, net_cfg, kind, data_dir)
        except Exception as e:
            if log:
                log.warning("board %s fetch failed: %s" % (kind, e))
            continue
        for row in rows:
            ent = conv(row)
            if not ent:
                continue
            nos = {_norm_no(row.get("hbh")), _norm_no(row.get("main_hbh"))}
            for no in nos:
                if not no:
                    continue
                fdb = db["flights"].setdefault(no, {"dows": {}})
                cur = fdb["dows"].get(dow)
                if cur is None:
                    fdb["dows"][dow] = ent
                    changed = True
                elif ent.get("dep") and ent.get("arr"):
                    # richest row (arrive board dual-time) replaces a
                    # dep-only one; today's board is the fresher source
                    fdb["dows"][dow] = ent
                    changed = True
                else:
                    # partial row (missing one time): only FILL missing
                    # fields, never erase an earlier stored time
                    for k in ("dep", "arr"):
                        if not cur.get(k) and ent.get(k):
                            cur[k] = ent[k]
                            changed = True
    if changed:
        db["updated"] = time.time()
        try:
            os.makedirs(data_dir, exist_ok=True)
            _atomic_write(db_path, db)
        except Exception as e:
            if log:
                log.warning("sched db write failed: %s" % e)
    _cleanup_board_cache(data_dir)
    return db


def load_sched_db(data_dir):
    try:
        with open(os.path.join(data_dir, DB_NAME), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"updated": 0, "flights": {}}


def sched_stats(db):
    """v0.20: coverage summary for the UI (pure, CI-testable).
    Counts flights with >=1 non-empty dow entry and a per-dow histogram;
    empty entries (None/{}) are ignored so the widget never lies."""
    dows = {}
    n_flights = 0
    for _no, fdb in (db.get("flights") or {}).items():
        have = [d for d, e in ((fdb or {}).get("dows") or {}).items() if e]
        if not have:
            continue
        n_flights += 1
        for d in have:
            dows[str(d)] = dows.get(str(d), 0) + 1
    return {
        "updated": float(db.get("updated") or 0),
        "flights": n_flights,
        "dows": {str(i): dows.get(str(i), 0) for i in range(7)},
    }


def board_lookup(db, flight_no, date_iso, from_city, to_city):
    """按 航班号+星期几+城市 匹配参考时刻. 返回 entry 或 None."""
    fdb = (db.get("flights") or {}).get(_norm_no(flight_no))
    if not fdb:
        return None
    try:
        dow = str(_dt.date.fromisoformat(date_iso).weekday())
    except Exception:
        return None
    ent = fdb.get("dows", {}).get(dow)
    if not ent:
        return None
    if from_city and ent.get("from") and from_city not in ent["from"] and ent["from"] not in from_city:
        return None
    if to_city and ent.get("to") and to_city not in ent["to"] and ent["to"] not in to_city:
        return None
    return ent


def board_lookup_x(db, flight_no, date_iso, from_city, to_city):
    """v0.19 跨日班期回退: 日历价已证明该航班号在该日期执飞, 而班期板只
    返回当日 -> 时刻库尚未沉淀该 dow 属常态. 同航班号时刻按航季排班,
    其他 dow 的时刻高度一致, 可作为参考借用(调用方需打 airport-board-x
    标记). 返回 (entry, exact_bool) 或 None; exact=dow 精确命中.
    跨日时优先选双时刻(dep+arr)且城市匹配的条目, 再退 dep-only."""
    fdb = (db.get("flights") or {}).get(_norm_no(flight_no))
    if not fdb:
        return None
    try:
        dow = str(_dt.date.fromisoformat(date_iso).weekday())
    except Exception:
        return None

    def _city_ok(ent):
        if from_city and ent.get("from") and from_city not in ent["from"] and ent["from"] not in from_city:
            return False
        if to_city and ent.get("to") and to_city not in ent["to"] and ent["to"] not in to_city:
            return False
        return True

    ent = fdb.get("dows", {}).get(dow)
    if ent and _city_ok(ent):
        return ent, True
    cands = [e for e in (fdb.get("dows") or {}).values() if e and _city_ok(e)]
    if not cands:
        return None
    dual = [e for e in cands if e.get("dep") and e.get("arr")]
    # dual-time rows carry the most info; otherwise prefer an entry that
    # at least has a dep time so the caller can still render the departure
    pool = dual or [e for e in cands if e.get("dep")] or cands
    return pool[0], False
