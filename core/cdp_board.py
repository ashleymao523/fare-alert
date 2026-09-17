# -*- coding: utf-8 -*-
"""v1.22: Ctrip flight-detail board (per-date plan times, any future
date) fetched through a real headed browser driven over CDP.

Why this exists: the Shanghai Avinex board only answers yesterday/
today/tomorrow, so obs rows dated further out can never self-heal -
the Beijing->Shanghai leg was stuck at 3/8 and Chongqing->Shanghai
had ZERO fnos in the sched db. Ctrip's actualtime detail page answers
per (flightNo, date) for any future date (verified 2026-09-17:
HO1254 @ 2026-10-25 -> Daxing T2 21:25 - Pudong 23:40, source
"feiyou"; 3U8971 @ 2026-10-16 -> CKG T3 07:15 - PVG T2 09:40).
Headless is blocked (whaleguard), so the browser is started minimized
and killed right after extraction; one page load per query.

红线 (mirrors sh_board.py): 6h per-(fno,date) row cache, a global
daily 24-query hard cap shared via board_fetch_log.json (kind
"ctrip_board", failed loads burn budget too), and a 24h negative
cache for flight numbers the page answers empty. force skips ONLY
the row cache - never the budget.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request

import websocket

from .sched_board import DB_NAME, _atomic_write

DETAIL_URL = ("https://flights.ctrip.com/actualtime/"
              "detail.html?flightNo={f}&date={d}")
CT_TTL = 6 * 3600
CT_NEG_TTL = 24 * 3600  # empty-detail pages are stable schedule facts
CT_DAILY_MAX = 24
CT_LOG_KIND = "ctrip_board"
CT_LOG_NAME = "board_fetch_log.json"  # shared with the SH/HGH boards
CT_PORT_DEFAULT = 9335
CT_WAIT_DEFAULT = 14

BS = chr(92)  # real backslash; template source must stay editable
_BROWSERS = (
    os.path.join("C:", BS, "Program Files (x86)", "Microsoft",
                 "Edge", "Application", "msedge.exe"),
    os.path.join("C:", BS, "Program Files", "Microsoft",
                 "Edge", "Application", "msedge.exe"),
    os.path.join("C:", BS, "Program Files", "Google",
                 "Chrome", "Application", "chrome.exe"),
)


def _norm_no(s):
    return "".join((s or "").split()).upper()


def _day(s):
    s = str(s or "").strip()[:10]
    try:
        return _dt.date.fromisoformat(s)
    except ValueError:
        return None


def _log_count(data_dir, today):
    try:
        with open(os.path.join(data_dir, CT_LOG_NAME),
                  encoding="utf-8") as f:
            log = json.load(f)
        return int((log.get(CT_LOG_KIND) or {}).get(today, 0))
    except Exception:
        return 0


def _bump_log(data_dir, today):
    path = os.path.join(data_dir, CT_LOG_NAME)
    log = {}
    try:
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    except Exception:
        pass
    days = log.setdefault(CT_LOG_KIND, {})
    days[today] = int(days.get(today, 0)) + 1
    cutoff = (_dt.date.today() - _dt.timedelta(days=3)).isoformat()
    for k in list(log):
        log[k] = {d: n for d, n in log[k].items() if d >= cutoff}
    try:
        os.makedirs(data_dir, exist_ok=True)
        _atomic_write(path, log)
    except Exception:
        pass


def _cache_path(data_dir, fno, date_iso):
    return os.path.join(data_dir, "board_ct_{f}_{d}.json".format(
        f=fno, d=str(date_iso).replace("-", "")))


def neg_hit(data_dir, fno, date_iso):
    """True when this (fno, date) was answered page-empty within the
    last 24h. Read-only; corrupt files read as not-neg."""
    try:
        with open(_cache_path(data_dir, fno, date_iso),
                  encoding="utf-8") as f:
            ent = json.load(f)
        return (not ent.get("row") and bool(ent.get("neg"))
                and time.time() - float(ent.get("ts") or 0)
                < CT_NEG_TTL)
    except Exception:
        return False


def _find_browser():
    for b in _BROWSERS:
        if os.path.exists(b):
            return b
    for name in ("msedge", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _js_extract(ws, sess, expr):
    """One Runtime.evaluate over a flat Target session."""
    ws.send(json.dumps({"id": 991, "method": "Runtime.evaluate",
                        "params": {"expression": expr,
                                   "returnByValue": True},
                        "sessionId": sess}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == 991:
            break
    return (((msg.get("result") or {}).get("result") or {})
            .get("value"))


JS_EXPR = """
                (function(){
                  var h = document.querySelector('.flight-detail-header');
                  var l = document.querySelector('.flight-detail-body-left');
                  if (!h || !l) return null;
                  return {header: h.innerText, left: l.innerText};
                })()
            """


def _launch_and_extract(net_cfg, data_dir, fno, date_iso):
    """Real browser page load -> raw header/left text. Raises when
    the browser or the page never becomes ready. The caller owns
    caching/ledger; this helper is pure I/O."""
    exe = _find_browser()
    if not exe:
        raise RuntimeError("no chrome/edge binary found")
    port = int(net_cfg.get("ctdp_port", CT_PORT_DEFAULT))
    profile = os.path.abspath(
        os.path.join(data_dir, "edge_prof_ctrip_board"))
    os.makedirs(profile, exist_ok=True)
    proc = subprocess.Popen(
        [exe,
         "--user-data-dir=" + profile,
         "--remote-debugging-port=" + str(port),
         "--no-first-run", "--no-default-browser-check",
         "--start-minimized", "--window-size=1280,900",
         "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        bws = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/json/version" % port,
                        timeout=2) as r:
                    bws = json.loads(r.read().decode())[
                        "webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(0.5)
        if not bws:
            raise RuntimeError("browser debug endpoint never opened")
        ws = websocket.create_connection(bws, timeout=15,
                                         suppress_origin=True)

        def rpc(method, params=None):
            ws.send(json.dumps({"id": 990, "method": method,
                                "params": params or {}}))
            while True:
                m = json.loads(ws.recv())
                if m.get("id") == 990:
                    break
            if m.get("error"):
                raise RuntimeError(str(m["error"])[:200])
            return m.get("result")

        targets_ = (rpc("Target.getTargets")
                    .get("targetInfos") or [])
        page = next((t for t in targets_
                     if t.get("type") == "page"), None)
        if not page:
            raise RuntimeError("no page target")
        sess = rpc("Target.attachToTarget",
                   {"targetId": page["targetId"],
                    "flatten": True})["sessionId"]
        ws.send(json.dumps({"id": 988, "method": "Page.navigate",
                            "params": {"url": DETAIL_URL.format(
                                f=fno, d=date_iso)},
                            "sessionId": sess}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 988:
                break
        wait = float(net_cfg.get("ct_wait", CT_WAIT_DEFAULT))
        deadline = time.time() + max(6.0, wait)
        ready = None
        while time.time() < deadline and not ready:
            time.sleep(1.2)
            ready = _js_extract(ws, sess, JS_EXPR)
        if not ready:
            raise RuntimeError("detail node never rendered")
        return ready
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass


cb_launch = _launch_and_extract  # indirection hook for test stubs


_HM = re.compile("(?:[01]?" + chr(92) + "d|2[0-3]):[0-5]"
                 + chr(92) + "d")


def parse_detail(header, left):
    """header/left innerText -> row dict (None when the page shows
    no data). Pure; raises nothing."""
    try:
        header = str(header or "")
        left = str(left or "")
        zh = chr(92) + "u4e00-" + chr(92) + "u9fa5"
        flat = header.replace(" ", "")
        mf = re.search("[A-Z0-9]{2}" + chr(92) + "d{3,4}", flat)
        if not mf:
            return None
        fno = _norm_no(mf.group(0))
        mair = re.search("([" + zh + "A-Za-z]+)",
                         flat[:mf.start()])
        airline = mair.group(1) if mair else ""
        times = _HM.findall(left)
        if len(times) < 2:
            return None
        dep, arr = times[0], times[1]
        lines = [x.strip() for x in re.split(
            "[" + chr(92) + "n|]", left) if x.strip()]
        cities = [ln for ln in lines
                  if not re.fullmatch("T[1-9]", ln.upper())]
        terms = [ln.upper() for ln in lines
                 if re.fullmatch("T[1-9]", ln.upper())]
        dep_city = cities[0] if cities else ""
        arr_city = cities[1] if len(cities) > 1 else ""
        dep_t = terms[0] if terms else ""
        arr_t = terms[1] if len(terms) > 1 else ""
        return {"fno": fno, "airline": airline, "dep": dep,
                "arr": arr, "from": dep_city, "to": arr_city,
                "dep_terminal": dep_t, "arr_terminal": arr_t,
                "src": "ctrip-detail"}
    except Exception:
        return None


def fetch_flight(net_cfg, data_dir, fno, date_iso, force=False):
    """One (fno, date) plan-time query. Returns (row|None, how) with
    how in ('net','cache','neg-cache','capped'); capped and neg-cache
    are quiet no-ops so a patrol round never errors out."""
    fno = _norm_no(fno)
    date_iso = str(date_iso)[:10]
    today = _dt.date.today().isoformat()
    path = _cache_path(data_dir, fno, date_iso)
    if not force and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                ent = json.load(f)
            if time.time() - float(ent.get("ts") or 0) < CT_TTL:
                if not ent.get("row") and ent.get("neg"):
                    return (None, "neg-cache")
                return (ent.get("row"), "cache")
        except Exception:
            pass
    if _log_count(data_dir, today) >= CT_DAILY_MAX:
        return (None, "capped")
    try:
        raw = cb_launch(net_cfg, data_dir, fno, date_iso)
    except Exception:
        _bump_log(data_dir, today)
        raise
    row = parse_detail((raw or {}).get("header"),
                       (raw or {}).get("left"))
    if row and row.get("fno") != fno:
        row = None
    os.makedirs(data_dir, exist_ok=True)
    _atomic_write(path, {"ts": time.time(), "row": row,
                         "neg": not row})
    _bump_log(data_dir, today)
    return (row, "net")


def targets(history, max_fnos=4, today=None):
    """Timeless obs rows -> one target per fno (its earliest missing
    date first). Pure; covers EVERY leg (city-agnostic by design)."""
    today = today or _dt.date.today()
    earliest = {}
    for rid, r in (history.get("routes") or {}).items():
        for o in (r.get("obs") or []):
            fno = _norm_no(o.get("fno"))
            if not fno or o.get("dep") or o.get("arr"):
                continue
            d = _day(o.get("date"))
            if d is None or d < today:
                continue
            if fno not in earliest or d < earliest[fno]:
                earliest[fno] = d
    out = [{"fno": f, "date": d.isoformat()}
           for f, d in sorted(earliest.items(), key=lambda kv: kv[1])]
    return out[:max(0, int(max_fnos))]


def _merge_row(db, row, date_iso):
    """Own-dow deposit with tier rules: airport-board stays
    authoritative; ctrip-detail and shanghai-board are one tier and
    refresh each other (per-date plan times shift); borrow loses."""
    d = _day(date_iso)
    if d is None or not row.get("dep") or not row.get("arr"):
        return False
    dow = str(d.weekday())
    fdb = db.setdefault("flights", {}).setdefault(
        row["fno"], {"dows": {}})
    ent = {"dep": row["dep"], "arr": row["arr"],
           "from": row.get("from", ""), "to": row.get("to", ""),
           "airline": row.get("airline", ""),
           "src": "ctrip-detail"}
    cur = fdb["dows"].get(dow)
    if cur is None:
        fdb["dows"][dow] = ent
        return True
    if cur.get("src") == "airport-board":
        changed = False
        for k in ("dep", "arr", "from", "to"):
            if not cur.get(k) and ent.get(k):
                cur[k] = ent[k]
                changed = True
        return changed
    if any(cur.get(k) != ent.get(k)
           for k in ("dep", "arr", "from", "to")):
        fdb["dows"][dow] = ent
        return True
    return False


def _apply_exact(history, row, date_iso, now=None):
    """Write the official times onto matching timeless obs rows
    (date x fno x from_city x to_city contract; existing real times
    are never overwritten). Returns the number of upgraded obs."""
    now = now or _dt.datetime.now().strftime("%Y-%m-%dT%H:%M")
    n = 0
    for rid, r in (history.get("routes") or {}).items():
        for o in (r.get("obs") or []):
            if (str(o.get("date") or "") != str(date_iso)
                    or _norm_no(o.get("fno")) != row["fno"]):
                continue
            if o.get("dep") or o.get("arr"):
                continue
            fc = str(r.get("from_city") or "")
            tc = str(r.get("to_city") or "")
            if row.get("from") and fc and fc not in row["from"]:
                continue
            if row.get("to") and tc and tc not in row["to"]:
                continue
            o["dep"] = row["dep"]
            o["arr"] = row["arr"]
            o["ts"] = now
            o["tsrc"] = "ctrip-detail"
            n += 1
    return n


def fill(net_cfg, data_dir, history, log=None, max_fnos=4,
         force=False):
    """Driver: pick targets, query each once, deposit into the sched
    db + history. Bounded (max_fnos), daily-capped; returns stats."""
    stats = {"queries": 0, "exact": 0, "filled": 0, "fnos": 0,
             "neg": 0, "capped": False}
    sched_path = os.path.join(data_dir, DB_NAME)
    try:
        with open(sched_path, encoding="utf-8") as f:
            db = json.load(f)
    except Exception:
        db = {"fmt": 2, "updated": 0, "flights": {}}
    changed_db = False
    changed_hist = False
    fails = 0
    for t in targets(history, max_fnos=max_fnos):
        if neg_hit(data_dir, t["fno"], t["date"]):
            stats["neg"] += 1
            continue
        try:
            row, how = fetch_flight(net_cfg, data_dir, t["fno"],
                                    t["date"], force=force)
        except Exception as e:
            fails += 1
            if log:
                log.warning("ctrip board %s@%s failed: %s",
                            t["fno"], t["date"], e)
            if fails >= 2:
                stats["breaker"] = True
                break
            continue
        fails = 0
        if how == "capped":
            stats["capped"] = True
            break
        if how == "net":
            stats["queries"] += 1
        elif how == "neg-cache":
            stats["neg"] += 1
        if row:
            stats["exact"] += _apply_exact(history, row, t["date"])
            if _merge_row(db, row, t["date"]):
                stats["filled"] += 1
                changed_db = True
            changed_hist = changed_hist or stats["exact"] > 0
        stats["fnos"] += 1
    if changed_db:
        db["updated"] = time.time()
        try:
            os.makedirs(data_dir, exist_ok=True)
            _atomic_write(sched_path, db)
        except Exception as e:
            if log:
                log.warning("ctrip board sched db write failed: %s", e)
    if changed_hist:
        try:
            from .cabin_monitor import _atomic_write \
                as cabin_atomic_write
            cabin_atomic_write(os.path.join(data_dir,
                                            "cabin_history.json"),
                               history)
        except Exception as e:
            if log:
                log.warning("ctrip board history write failed: %s", e)
    return stats
