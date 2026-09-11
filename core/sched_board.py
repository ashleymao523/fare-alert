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


def _via_city(field):
    """Stop city: '青岛/胶东' -> '青岛'; [] / list / None safe."""
    if isinstance(field, (list, tuple)):
        field = field[0] if field else ""
    return _city(field)


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
    # v0.32: nextschtime = scheduled arrival at the NEXT point. For
    # nonstop rows that is the final destination -> a real arr time from
    # the same zero-key board (no extra request). For stopover rows it
    # is the STOP city arrival: storing it as the final arr would lie,
    # so keep arr empty and record the stop as metadata only.
    via = _via_city(row.get("chinese_jtcs"))
    arr = "" if via else _hhmm(row.get("nextschtime"))
    return {
        "dep": _hhmm(row.get("jhsj")),
        "arr": arr,
        "from": _city(row.get("chinese_sfcs")),
        "to": _city(row.get("chinese_mdcs")),
        "via": via,
        "via_arr": _hhmm(row.get("nextschtime")) if via else "",
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


def _merge_board_rows(db, rows, conv, dow):
    """Merge one board's rows into db under dow. Returns True when the
    db actually changed (idempotent for identical replays)."""
    changed = False
    for row in rows or []:
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
                # dict(ent): codeshare aliases must not share one object
                fdb["dows"][dow] = dict(ent)
                changed = True
            elif ent.get("dep") and ent.get("arr"):
                # richest row (dual-time) replaces a dep-only one; only
                # flag a change when content actually differs so cache
                # replays stay idempotent. Carry over via metadata the
                # stored entry may already hold: an arrive-board dual row
                # has no via keys and would otherwise drop them.
                merged = dict(ent)
                for k in ("via", "via_arr"):
                    if cur.get(k) and not merged.get(k):
                        merged[k] = cur[k]
                if any(merged.get(k) != cur.get(k)
                       for k in ("dep", "arr", "via", "via_arr",
                                 "from", "to")):
                    fdb["dows"][dow] = merged
                    changed = True
            else:
                # partial row (missing one time): only FILL missing
                # fields, never erase an earlier stored time
                for k in ("dep", "arr", "via", "via_arr"):
                    if not cur.get(k) and ent.get(k):
                        cur[k] = ent[k]
                        changed = True
    return changed


def backfill_from_cache(data_dir, log=None, db=None):
    """v0.32: one-shot offline db upgrade from cached board files.

    Re-merges every board_(leave|arrive)_YYYY-MM-DD.json still in the
    cache window through the CURRENT converters. Zero network requests
    (pure local replay): upgrades an old-format db (leave rows stored
    without the nextschtime arrival) as soon as the converter learns to
    extract more, without waiting a full week for each dow to re-fetch.
    Idempotent by merge rules. Pass db= to merge into a dict already
    loaded by the caller (update_sched_db) so both write the same object;
    when omitted the db is loaded from disk here. Returns stats.
    """
    import glob
    import re as _re
    db_path = os.path.join(data_dir, DB_NAME)
    if db is None:
        db = {"updated": 0, "flights": {}}
        try:
            with open(db_path, encoding="utf-8") as f:
                db = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as e:
            # same guard as update_sched_db: never silently wipe a
            # half-written db when replaying caches standalone
            try:
                os.replace(db_path, "%s.corrupt-%d"
                           % (db_path, int(time.time())))
            except Exception:
                pass
            if log:
                log.warning("sched db unreadable, backed up + rebuilding: %s"
                            % e)
            pass
    changed = False
    files = 0
    for path in sorted(glob.glob(os.path.join(data_dir, "board_*.json"))):
        m = _re.match(r"board_(leave|arrive)_(\d{4}-\d{2}-\d{2})\.json$",
                      os.path.basename(path))
        if not m:
            continue
        kind, day = m.group(1), m.group(2)
        try:
            with open(path, encoding="utf-8") as f:
                ent = json.load(f)
            rows = ent.get("rows") or []
        except Exception as e:
            if log:
                log.warning("backfill skip %s: %s" % (os.path.basename(path), e))
            continue
        files += 1
        try:
            dow = str(_dt.date.fromisoformat(day).weekday())
        except ValueError:
            continue
        conv = _entry_from_leave if kind == "leave" else _entry_from_arrive
        changed = _merge_board_rows(db, rows, conv, dow) or changed
    if changed:
        db["updated"] = time.time()
        try:
            os.makedirs(data_dir, exist_ok=True)
            _atomic_write(db_path, db)
        except Exception as e:
            if log:
                log.warning("backfill db write failed: %s" % e)
    return {"files": files, "changed": changed}


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
    changed = backfill_from_cache(data_dir, log, db=db)["changed"]
    for kind, conv in (("leave", _entry_from_leave), ("arrive", _entry_from_arrive)):
        try:
            rows, cached = fetch_board(session, net_cfg, kind, data_dir)
        except Exception as e:
            if log:
                log.warning("board %s fetch failed: %s" % (kind, e))
            continue
        changed = _merge_board_rows(db, rows, conv, dow) or changed
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
    跨日时优先选双时刻(dep+arr)且城市匹配的条目, 再退 dep-only.

    v0.22 城市分层匹配(经停友好):
    板上存的是航班最终经停点(如 杭州->克拉玛依 的 GJ8069 实际经停郑州),
    按"最终到达城市"硬过滤会误杀经停航段. 同一航班号在同机场同 dow 只有一班,
    出发时刻与最终终点无关 -> 城市匹配降级为分层偏好:
      tier0 出发+到达都匹配 > tier1 仅出发侧匹配(经停/终到不同) >
      tier2 仅到达侧匹配 > tier3 都不匹配.
    dow 精确命中: 板是机场维数据(号+dow+机场唯一), 任何 tier 都算 exact.
    跨 dow 借用: 只接受 tier0/tier1(出发侧必须一致, 拒绝跨航线误借)."""
    def _as_dest(ent):
        """Through-flight hop-off: the deal's destination IS the stored
        stop city -> the stop arrival (via_arr, same board row) is that
        passenger's real arrival. Expose it as arr."""
        if to_city and ent and not ent.get("arr") and ent.get("via"):
            if to_city in ent["via"] or ent["via"] in to_city:
                e = dict(ent)
                e["arr"] = e.get("via_arr") or ""
                return e
        return ent

    fdb = (db.get("flights") or {}).get(_norm_no(flight_no))
    if not fdb:
        return None
    try:
        dow = str(_dt.date.fromisoformat(date_iso).weekday())
    except Exception:
        return None

    def _from_ok(ent):
        if not from_city or not ent.get("from"):
            return True
        return from_city in ent["from"] or ent["from"] in from_city

    def _to_ok(ent):
        if not to_city or not ent.get("to"):
            return True
        return to_city in ent["to"] or ent["to"] in to_city

    def _tier(ent):
        fm, tm = _from_ok(ent), _to_ok(ent)
        if fm and tm:
            return 0
        if fm:
            return 1
        if tm:
            return 2
        return 3

    def _city_ok(ent):
        return _tier(ent) <= 1

    ent = fdb.get("dows", {}).get(dow)
    if ent:
        # 号+dow+机场 唯一确定一班, 城市不匹配只是经停终点不同 -> 仍算精确
        return _as_dest(ent), True
    cands = [e for e in (fdb.get("dows") or {}).values() if e and _city_ok(e)]
    if not cands:
        return None
    cands.sort(key=lambda e: _tier(e))
    dual = [e for e in cands if e.get("dep") and e.get("arr")]
    # dual-time rows carry the most info; otherwise prefer an entry that
    # at least has a dep time so the caller can still render the departure
    pool = dual or [e for e in cands if e.get("dep")] or cands
    return _as_dest(pool[0]), False


def _hhmm_min(t):
    try:
        return int(t[:2]) * 60 + int(t[3:5])
    except (TypeError, ValueError, IndexError):
        return None


def build_route_priors(db, min_samples=3):
    """v0.25 route duration priors from the arrive-board dual-time rows.

    Every arrive-board entry stores preschtime (upstream dep) + jhsj
    (HGH arr): the REAL flown minutes of the CITY->Hangzhou leg. The same
    physical route flown HGH->CITY takes nearly the same time (route
    winds shift it by ~5-15min), which beats the great-circle guess
    (taxi/detour/holding often 30min+ off) for the outbound arr_est.

    Returns {from_city: {'minutes': median, 'n': hits}} built from
    entries with dep+arr present; median is robust to delays/outliers.
    Pure function over the db dict -> CI-testable without network."""
    import statistics
    buckets = {}
    seen = set()
    for fdb in (db.get("flights") or {}).values():
        for ent in (fdb.get("dows") or {}).values():
            if not ent or not ent.get("dep") or not ent.get("arr"):
                continue
            city = (ent.get("from") or "").strip().replace("机场", "")
            if not city or "杭州" in city:
                continue
            d, a = _hhmm_min(ent["dep"]), _hhmm_min(ent["arr"])
            if d is None or a is None:
                continue
            if a < d:  # red-eye lands next day
                a += 24 * 60
            mins = a - d
            if not 45 <= mins <= 17 * 60:  # reject garbage rows
                continue
            # codeshare rows repeat one physical flight under several
            # numbers (same dep+arr): count each time pair once or the
            # duplicate mass flips the median (v0.25 review P1)
            key = (city, d, a)  # parsed minutes: "8:00"/"08:00" dedupe too
            if key in seen:
                continue
            seen.add(key)
            buckets.setdefault(city, []).append(mins)
    out = {}
    for city, vals in buckets.items():
        if len(vals) < min_samples:
            continue
        # a stopover flight's preschtime is the LAYOVER station's dep,
        # not the origin city's: its minutes cover only the last leg.
        # Full-trip minutes are physically >= last-leg ones for the same
        # city, so split the samples into gap clusters and keep the
        # biggest-median cluster with enough samples (= nonstop whole leg).
        vals.sort()
        clusters = [[vals[0]]]
        for v in vals[1:]:
            if v - clusters[-1][-1] > 75:
                clusters.append([v])
            else:
                clusters[-1].append(v)
        good = [c for c in clusters if len(c) >= min_samples]
        if good:
            best = max(good, key=lambda c: statistics.median(c))
            med = int(statistics.median(best))
            # stopover-only city guard (v0.25.1): when EVERY row of a city
            # is a stopover trip, its last-leg cluster masquerades as a
            # full-trip prior (Lhasa 150min vs real ~280min). A real
            # nonstop can never beat great-circle @900km/h + 30min taxi,
            # so drop the prior when the median is below that floor.
            try:
                from core.intl import city_iata
                from core.flights import AIRPORT_COORDS, _haversine_km
                b = AIRPORT_COORDS.get((city_iata(city) or "").upper())
                a = AIRPORT_COORDS.get("HGH")
                if a and b and med < _haversine_km(a, b) / 900.0 * 60 + 30:
                    continue
            except Exception:
                pass  # unresolvable city: keep prior (old behavior)
            out[city] = {"minutes": med, "n": len(best)}
    return out


def prior_minutes_for(priors, city):
    """Lookup a duration prior for a route city. Intl board keys are
    'city + airport' ('曼谷素万那普'), while routes say '曼谷': fall back
    to prefix matches and take the busiest airport's prior (same metro
    area, flight-time difference is negligible)."""
    city = (city or "").strip()
    if not city:
        return None
    p = priors.get(city)
    if p:
        return p["minutes"]
    cands = [(v["n"], v["minutes"]) for k, v in priors.items()
             if k.startswith(city)]
    if not cands:
        return None
    cands.sort(reverse=True)
    return cands[0][1]


def city_dep_times(db, to_city, date_iso, limit=4):
    """v0.26 numberless-deal helper: known HGH->to_city departures for the
    date's dow, so intl calendar deals (price-only, no flight number) can
    still show real departure times. Board rows store the final destination
    ('曼谷素万那普机场'), so match by city substring; cross-dow borrowed
    entries are flagged exact=False (same flight number, same season ->
    the time is a strong reference, the UI badges it). Pure over db dict."""
    city = (to_city or "").strip()
    if not city:
        return []
    try:
        dow = str(_dt.date.fromisoformat(date_iso).weekday())
    except Exception:
        return []
    out = []
    for no, fdb in (db.get("flights") or {}).items():
        dows = fdb.get("dows") or {}
        if not dows:
            continue
        exact = dows.get(dow) or {}
        ent = exact
        if not (ent or {}).get("dep"):
            # cross-dow: any day's dep for the same flight number
            ent = next((e for e in dows.values()
                        if (e or {}).get("dep")), {})
        if not ent.get("dep"):
            continue
        if "杭州" not in (ent.get("from") or ""):
            continue
        if city not in (ent.get("to") or ""):
            continue
        dep = str(ent["dep"])[:5]
        out.append({"no": no, "dep": dep,
                    "exact": bool((exact or {}).get("dep"))})
    out.sort(key=lambda x: (not x["exact"], x["dep"]))
    # codeshare rows repeat one physical flight under several numbers:
    # keep one entry per time slot (exact-first sort makes the exact one
    # survive), so the UI list stays readable
    seen_dep, dedup = set(), []
    for e in out:
        if e["dep"] in seen_dep:
            continue
        seen_dep.add(e["dep"])
        dedup.append(e)
    return dedup[:limit]
