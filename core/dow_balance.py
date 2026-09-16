# -*- coding: utf-8 -*-
"""v1.07 dow balance: the board db sediments one dow per day the
box is awake (update_sched_db files today's board under today's
weekday). A box that sleeps weekends NEVER sees a Saturday/Sunday
board - the live db shows dow0-4 at 3000+ rows, dow5 at ~900 and
dow6 at ZERO - so every weekend departure keeps its weak booking-x
pin forever, even though a precise point query (the user's standing
observation) answers with a full same-day offer list.

balance_once detects starved dows, probes ONE future date per
(starved dow x Hangzhou route direction) through the existing
fetch_lowest pipeline, and queues the returned timetable rows into
the sched_deposit queue, then absorbs them right away so the same
cycle's rows already enjoy exact board hits. absorb_deposit files
each row under its own weekday and existing entries always win, so
repeated runs can never corrupt observed board data."""
import datetime as _dt
import json
import os
import time

STATE_NAME = "dow_balance.json"
RUN_TTL = 12 * 3600          # one balance round per 12h max
DONE_TTL = 7 * 86400         # never re-probe the same dow+date+pair
DOW_RATIO = 0.35             # dow count below peak*35% => starved
DOW_FLOOR = 60               # ... or below this absolute floor
WINDOW_LO, WINDOW_HI = 2, 25  # probe dates: +2..+25 days out

_HGH_KEYS = ("杭州", "hangzhou", "hgh", "xiaoshan")


def _state_path(data_dir):
    return os.path.join(data_dir, STATE_NAME)


def _atomic_write(path, obj):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def dow_coverage(db):
    """{dow(str 0-6): n_entries} across the whole board db."""
    counts = {str(i): 0 for i in range(7)}
    for f in (db.get("flights") or {}).values():
        for dow in (f.get("dows") or {}):
            k = str(dow)
            if k in counts:
                counts[k] += 1
    return counts


def weak_dows(db, ratio=DOW_RATIO, floor=DOW_FLOOR):
    """Starved weekday numbers (ints) - coverage below max(floor,
    peak*ratio). Weekend-off boxes yield [5, 6] (Python weekday:
    5=Sat, 6=Sun)."""
    counts = dow_coverage(db)
    peak = max(counts.values()) if counts else 0
    if peak <= 0:
        return []
    bar = max(int(floor), peak * float(ratio))
    return [i for i in range(7) if counts[str(i)] < bar]


def _next_date(dow, today=None, lo=WINDOW_LO, hi=WINDOW_HI):
    """Nearest date (+lo..+hi days out) whose weekday == dow, ISO
    str, or '' when the window misses (dow out of range)."""
    if dow not in range(7):
        return ""
    today = today or _dt.date.today()
    for off in range(int(lo), int(hi) + 1):
        d = today + _dt.timedelta(days=off)
        if d.weekday() == dow:
            return d.isoformat()
    return ""


def _route_hgh(r):
    blob = (str(r.get("from_city") or r.get("from") or "")
            + " " + str(r.get("to_city") or r.get("to") or "")).lower()
    return any(k in blob for k in _HGH_KEYS)


def _route_pair(r):
    """(fi, ti, from_city, to_city) with iata fallbacks."""
    fc = str(r.get("from_city") or r.get("from") or "")
    tc = str(r.get("to_city") or r.get("to") or "")
    fi = (str(r.get("from_iata") or "").strip().upper())
    ti = (str(r.get("to_iata") or "").strip().upper())
    if not fi and fc:
        try:
            from .intl import city_iata
            fi = city_iata(fc)
        except Exception:
            fi = ""
    if not ti and tc:
        try:
            from .intl import city_iata
            ti = city_iata(tc)
        except Exception:
            ti = ""
    return fi, ti, fc, tc


def balance_once(session, net_cfg, cfg, db, data_dir, log=None,
                 fetch=None, now=None):
    """One throttled balance round. Returns stats dict; never
    raises - the caller's pipeline must stay alive."""
    def _log(msg):
        if log:
            try:
                log.info(msg)
            except Exception:
                pass

    stats = {"weak": [], "probed": 0, "queued": 0, "absorbed": 0}
    try:
        now = now if now is not None else time.time()
        weak = weak_dows(db)
        stats["weak"] = weak
        if not weak:
            return stats
        routes = [r for r in (cfg.get("routes") or [])
                  if isinstance(r, dict) and _route_hgh(r)]
        if not routes:
            return stats
        # throttle: one round per RUN_TTL
        state = {}
        try:
            with open(_state_path(data_dir), encoding="utf-8") as f:
                state = json.load(f)
            state = state if isinstance(state, dict) else {}
        except Exception:
            state = {}
        if now - float(state.get("last_run") or 0) < RUN_TTL:
            return stats
        done = {k: v for k, v in (state.get("done") or {}).items()
                if now - float(v or 0) < DONE_TTL}
        if fetch is None:
            from .booking_fill import fetch_lowest as fetch
        from .point_fill import queue_sched_deposit
        from .sched_board import absorb_deposit, DB_NAME
        state["last_run"] = now
        touched = False
        for dow in weak:
            date = _next_date(dow)
            if not date:
                continue
            for r in routes:
                fi, ti, fc, tc = _route_pair(r)
                if not (fi and ti):
                    continue
                key = "%d|%s|%s%s" % (dow, date, fi, ti)
                if key in done:
                    continue
                done[key] = now
                touched = True
                stats["probed"] += 1
                try:
                    got = fetch(session, net_cfg, fi, ti, date)
                except Exception as e:
                    _log("dow-balance probe %s %s->%s failed: %s"
                         % (date, fi, ti, e))
                    continue
                if not got or got.get("no_data"):
                    _log("dow-balance %s %s->%s: no offers"
                         % (date, fi, ti))
                    continue
                rows = []
                for of in (got.get("offers") or []):
                    no = str(of.get("no") or "").strip().upper()
                    dep = str(of.get("dep") or "").strip()[:5]
                    arr = str(of.get("arr") or "").strip()[:5]
                    if no and (dep or arr):
                        rows.append({
                            "flight_no": no, "dep_time": dep,
                            "arr_time": arr, "date": date,
                            "from_city": fc, "to_city": tc,
                        })
                if rows:
                    stats["queued"] += queue_sched_deposit(
                        data_dir, rows)
                    _log("dow-balance %s (%s) %s->%s: %d rows queued"
                         % (date, ["Mon", "Tue", "Wed", "Thu", "Fri",
                                   "Sat", "Sun"][dow], fi, ti,
                            len(rows)))
        state["done"] = done
        try:
            os.makedirs(data_dir, exist_ok=True)
            _atomic_write(_state_path(data_dir), state)
        except Exception as e:
            _log("dow-balance state write failed: %s" % e)
        if stats["queued"]:
            db, n = absorb_deposit(data_dir, db, log)
            stats["absorbed"] = n
            if n:
                db["updated"] = time.time()
                try:
                    os.makedirs(data_dir, exist_ok=True)
                    _atomic_write(os.path.join(data_dir, DB_NAME), db)
                except Exception as e:
                    _log("dow-balance db write failed: %s" % e)
                _log("dow-balance absorbed %d rows into starved dows %s"
                     % (n, weak))
        elif not touched:
            # nothing new probed this round: push last_run back so the
            # next cycle (maybe new routes/dates) is not locked out
            state["last_run"] = 0
            try:
                _atomic_write(_state_path(data_dir), state)
            except Exception:
                pass
        return stats
    except Exception as e:      # never break the scan pipeline
        _log("dow-balance round failed: %s" % e)
        return stats
