# -*- coding: utf-8 -*-
"""v1.27: real-browser (CDP) precise business-cabin capture.

Recon verdict (2026-09-17, data/recon_qunar_cabin.json): the qunar
TOUCH flight list renders 200+ exact cards (flight no + dep/arr +
pay price) in a headed browser; the API stays signature-gated and
headless dumps show nothing (v0.76 archive). Tapping through the
filter drawer (筛选 -> 舱位 -> 公务/头等舱 -> 确定) re-renders the
list with BUSINESS prices (verified: MU5231 flipped 370 -> 1075).

This module drives ONE browser for a batch of route-day targets and
deposits the mined cards through the SAME point-fill cache the
bookmarklet uses (put_rows with the cabin tag) - the cabin watch
absorbs them with zero new plumbing.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import datetime as dt
import urllib.parse
import urllib.request

PORT = 9341

_BROWSERS = (
    os.path.expandvars("%ProgramFiles(x86)%\\Microsoft\\Edge"
                      "\\Application\\msedge.exe"),
    os.path.expandvars("%ProgramFiles%\\Microsoft\\Edge"
                      "\\Application\\msedge.exe"),
    os.path.expandvars("%ProgramFiles%\\Google\\Chrome"
                      "\\Application\\chrome.exe"),
    os.path.expandvars("%ProgramFiles(x86)%\\Google\\Chrome"
                      "\\Application\\chrome.exe"),
    os.path.expandvars("%LocalAppData%\\Google\\Chrome\\Application"
                      "\\chrome.exe"),
)

TAP_FILTER_JS = ("(function(){var all="
                 "document.querySelectorAll('div,span,li,section,a,button');"
                 "for(var i=0;i<all.length;i++){"
                 "var t=(all[i].textContent||'').trim();"
                 "if(t==='\u7b5b\u9009'){all[i].click();"
                 "return 'filter-opened';}}return 'filter-not-found';})()")

TAP_CABIN_ROW_JS = ("(function(){var all="
                    "document.querySelectorAll('div,span,li,section,a,button,label');"
                    "for(var i=0;i<all.length;i++){"
                    "var t=(all[i].textContent||'').trim();"
                    "if(t==='\u8231\u4f4d'){all[i].click();"
                    "return 'cabin-row-opened';}}"
                    "return 'cabin-row-not-found';})()")

TAP_BIZ_JS = ("(function(){var hits=[];var all="
              "document.querySelectorAll('div,span,li,section,a,button,label');"
              "for(var i=0;i<all.length;i++){"
              "var t=(all[i].textContent||'').trim();"
              "if(t&&t.length<=12&&t.indexOf('\u516c\u52a1')>=0){"
              "hits.push(all[i]);}}"
              "if(hits.length){hits[hits.length-1].click();"
              "return 'biz-tapped:'+hits.length;}"
              "return 'biz-chip-not-found';})()")

TAP_CONFIRM_JS = ("(function(){var all="
                  "document.querySelectorAll('div,span,li,section,a,button');"
                  "var words=['\u786e\u5b9a','\u5b8c\u6210','\u5e94\u7528'];"
                  "for(var w=0;w<words.length;w++){"
                  "for(var i=all.length-1;i>=0;i--){"
                  "var t=(all[i].textContent||'').trim();"
                  "if(t===words[w]){all[i].click();"
                  "return 'confirmed:'+words[w];}}}"
                  "return 'confirm-not-found';})()")

MINER_JS = """
(function(){
var FNO=/([A-Z][A-Z0-9])\\s?(\\d{3,4})/;
function times(s){var out=[],re=/(\\d{1,2}:\\d{2})/,m;
while(out.length<2&&s&&(m=re.exec(s))){out.push(m[1]);s=s.slice(m.index+m[1].length);}
return out;}
function cardOf(el){for(var up=0,a=el;up<7&&a;a=a.parentElement,up++){
var t=a.innerText||"";if(FNO.test(t)&&/\\d{1,2}:\\d{2}/.test(t)){return a;}}return null;}
var best=null,pnodes=document.querySelectorAll("[class*=price]");
for(var i=0;i<pnodes.length;i++){
var pd=(pnodes[i].textContent||"").replace(/[^\\d]/g,"");
if(!pd){continue;}
var pp=parseInt(pd,10);
if(!(pp>=50&&pp<=99999)){continue;}
var card=cardOf(pnodes[i]);
if(!card){continue;}
var ct=card.innerText||"";
var fm=ct.match(FNO);
if(!fm){continue;}
var ts=times(ct);
if(!best||pp<best.p){best={p:pp,no:fm[1]+fm[2],dep:ts[0]||"",arr:ts[1]||""};}}
return best;
})()
"""


LIST_MINER_JS = """
(function(){
var FNO=/([A-Z][A-Z0-9])\\s?(\\d{3,4})/;
function times(s){var out=[],re=/(\\d{1,2}:\\d{2})/,m;
while(out.length<2&&s&&(m=re.exec(s))){out.push(m[1]);s=s.slice(m.index+m[1].length);}
return out;}
function cardOf(el){for(var up=0,a=el;up<7&&a;a=a.parentElement,up++){
var t=a.innerText||"";if(FNO.test(t)&&/\\d{1,2}:\\d{2}/.test(t)){return a;}}return null;}
var seen={},pnodes=document.querySelectorAll("[class*=price]");
for(var i=0;i<pnodes.length;i++){
var pd=(pnodes[i].textContent||"").replace(/[^\\d]/g,"");
if(!pd){continue;}
var pp=parseInt(pd,10);
if(!(pp>=50&&pp<=99999)){continue;}
var card=cardOf(pnodes[i]);
if(!card){continue;}
var ct=card.innerText||"";
var fm=ct.match(FNO);
if(!fm){continue;}
var no=fm[1]+fm[2];var ts=times(ct);
var r={p:pp,no:no,dep:ts[0]||"",arr:ts[1]||""};
if(!seen[no]||pp<seen[no].p){seen[no]=r;}}
var rows=[];for(var k in seen){rows.push(seen[k]);}
rows.sort(function(a,b){return a.p-b.p;});
return rows.slice(0,12);
})()
"""


def _tap_plan(cabin):
    """v1.31: business/first needs the verified 4-tap filter dance;
    the DEFAULT touch list already IS the economy board - zero taps,
    straight to mining the whole visible card list."""
    if str(cabin or "").strip().lower() in ("business", "first"):
        return [TAP_FILTER_JS, TAP_CABIN_ROW_JS, TAP_BIZ_JS,
                TAP_CONFIRM_JS]
    return []


SCROLL_STEP_JS = ("(function(){window.scrollBy(0,700);"
                  "return 'scrolled';})()")


def list_url(fc, tc, date):
    q = urllib.parse.urlencode({
        "depCity": fc, "arrCity": tc, "goDate": date,
        "from": "touch_index_search"})
    return "https://m.flight.qunar.com/ncs/page/flightlist?" + q


def find_browser():
    for b in _BROWSERS:
        if os.path.exists(b):
            return b
    for name in ("msedge", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _kill_stale(profile_name):
    """Leftover children hold the debug port (proc.kill only reaps the
    launcher) - sweep them before launching."""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'"
         " -or Name='chrome.exe'\" | Where-Object {$_.CommandLine"
         " -match '" + profile_name + "'} | ForEach-Object {"
         " Stop-Process -Id $_.ProcessId -Force }"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)


def _tree_kill(proc):
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=15)
    except Exception:
        pass


def _seed_profile(profile):
    """A FRESH profile hits the touch login wall (verified: first recon
    run bounced to login.jsp) - seed the persistent capture profile
    once from whichever warmed profile already exists on this box."""
    if os.path.isdir(profile) and os.listdir(profile):
        return
    base = os.path.dirname(profile)
    for cand in ("edge_prof_recon_warm", "edge_prof_ctrip_board"):
        src = os.path.join(base, cand)
        if os.path.isdir(src):
            try:
                shutil.copytree(src, profile, dirs_exist_ok=True)
                return
            except Exception:
                continue


class _CDP:
    """Minimal flat-session CDP client with one reconnect retry (the
    renderer swap drops sessions mid-nav - same failure cdp_board
    tolerates by design)."""

    def __init__(self, bws):
        import websocket
        self._websocket = websocket
        self._bws = bws
        self.ws = None
        self.sess = None
        self.tid = None

    def connect(self):
        self.ws = self._websocket.create_connection(
            self._bws, timeout=15, suppress_origin=True)

    def rpc(self, method, params=None, mid=990):
        self.ws.send(json.dumps({"id": mid, "method": method,
                                 "params": params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                break
        if m.get("error"):
            raise RuntimeError(str(m["error"])[:200])
        return m.get("result")

    def open_tab(self, url):
        self.tid = self.rpc("Target.createTarget",
                            {"url": url})["targetId"]
        self.sess = self.rpc("Target.attachToTarget",
                             {"targetId": self.tid,
                              "flatten": True})["sessionId"]

    def nav(self, url, mid=988):
        self.ws.send(json.dumps({"id": mid, "method": "Page.navigate",
                                 "params": {"url": url},
                                 "sessionId": self.sess}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == mid:
                break

    def ev(self, expr, mid=991):
        for attempt in (0, 1):
            try:
                self.ws.send(json.dumps({
                    "id": mid, "method": "Runtime.evaluate",
                    "params": {"expression": expr,
                               "returnByValue": True},
                    "sessionId": self.sess}))
                while True:
                    m = json.loads(self.ws.recv())
                    if m.get("id") == mid:
                        break
                return (((m.get("result") or {}).get("result") or {})
                        .get("value"))
            except Exception:
                if attempt:
                    raise
                time.sleep(1.2)
                try:
                    self.ws.close()
                except Exception:
                    pass
                self.connect()
                self.sess = self.rpc("Target.attachToTarget",
                                     {"targetId": self.tid,
                                      "flatten": True})["sessionId"]


def _scroll_mine(cdp, deadline, cap=12, dry_stop=3, step_s=1.8):
    """v1.32: shared virtual-scroll list miner.

    The touch list is VIRTUAL - cards scrolled past leave the DOM,
    so a single mine sees only the viewport. Walk the page in 700px
    steps, mine each viewport, merge by fno (min price) until the
    feed stops yielding new flights or the deadline hits. Used by
    BOTH the economy board (no taps) and the cabin-filtered board
    (post 4-tap) so one session banks every visible offer."""
    seen = {}
    dry = 0
    while time.time() < deadline:
        time.sleep(step_s)
        try:
            got = cdp.ev(LIST_MINER_JS) or []
        except Exception:
            got = []
        fresh = 0
        for r in got:
            no = str(r.get("no") or "")
            if not no:
                continue
            try:
                pr = float(r.get("p"))
            except (TypeError, ValueError):
                continue
            if no not in seen or pr < seen[no]["p"]:
                seen[no] = {"p": pr, "no": no,
                            "dep": r.get("dep") or "",
                            "arr": r.get("arr") or ""}
                fresh += 1
        dry = 0 if fresh else dry + 1
        if len(seen) >= cap or dry >= dry_stop:
            break
        try:
            cdp.ev(SCROLL_STEP_JS)
        except Exception:
            pass
    return seen


def _capture_target(cdp, fc, tc, d, cabin, data_dir, log=None,
                    wait_s=12.0, rows_sink=None, cache_id=None,
                    tax=0.0):
    """v1.31: capture ONE (route, date) on an already-open CDP tab.
    business/first keeps the v1.27 4-tap filter dance + min-card
    miner; cabin="" (economy) skips every tap - the default touch
    list IS the economy board - and mines the WHOLE visible card
    list so the day detail can paint exact per-flight dep/arr.
    Returns n rows stored; rows_sink (a list) collects the captured
    rows for callers that want the full set, not just the lowest."""
    try:
        cdp.nav(list_url(fc, tc, d))
        time.sleep(4.0)
        wall = cdp.ev("location.href")
        if wall and "login" in str(wall):
            if log:
                log("cdp-cabin {fc}->{tc} {d}: login-wall "
                    "(warm the profile once in a real "
                    "browser)".format(fc=fc, tc=tc, d=d))
            return 0
        taps = []
        plan = _tap_plan(cabin)
        for js in plan:
            taps.append(cdp.ev(js))
            time.sleep(2.0 if js is TAP_FILTER_JS else 1.5)
        rows = []
        cab_tag = str(cabin or "").strip().lower() or "business"
        if plan:
            # v1.32: the cabin-filtered list is itself virtual-
            # scrolled - mine the WHOLE filtered board so one
            # session banks every business/first offer (v1.27
            # could only see the single min card). The v1.27
            # single-card miner stays as the fallback for pages
            # that render one summary card instead of a list.
            time.sleep(1.0)
            deadline = time.time() + max(8.0, wait_s)
            seen = _scroll_mine(cdp, deadline)
            best = None
            if not seen:
                while time.time() < deadline:
                    time.sleep(2.0)
                    best = cdp.ev(MINER_JS)
                    if best and best.get("p") and best.get("no"):
                        break
            for r in sorted(seen.values(), key=lambda x: x["p"]):
                try:
                    rows.append({
                        "date": d, "total": float(r.get("p")),
                        "flight_no": str(r.get("no") or ""),
                        "dep_time": str(r.get("dep") or ""),
                        "arr_time": str(r.get("arr") or ""),
                        "cabin": cab_tag,
                        "from_city": fc, "to_city": tc})
                except (TypeError, ValueError):
                    continue
            if not rows and best and best.get("p") \
                    and best.get("no"):
                rows = [{"date": d, "total": best["p"],
                         "flight_no": best["no"],
                         "dep_time": best.get("dep") or "",
                         "arr_time": best.get("arr") or "",
                         "cabin": cab_tag,
                         "from_city": fc, "to_city": tc}]
        else:
            deadline = time.time() + max(10.0, wait_s)
            seen = _scroll_mine(cdp, deadline)
            for r in sorted(seen.values(), key=lambda x: x["p"]):
                try:
                    rows.append({
                        "date": d, "total": float(r.get("p")),
                        "flight_no": str(r.get("no") or ""),
                        "dep_time": str(r.get("dep") or ""),
                        "arr_time": str(r.get("arr") or ""),
                        "cabin": "", "from_city": fc, "to_city": tc})
                except (TypeError, ValueError):
                    continue
        n = 0
        if rows:
            from core.point_fill import put_rows
            _, n = put_rows(
                data_dir,
                cache_id or "cdp-cabin-{fc}-{tc}".format(fc=fc, tc=tc),
                rows, tax=float(tax or 0.0))
            if rows_sink is not None:
                try:
                    rows_sink.extend(rows)
                except Exception:
                    pass
        if log:
            log("cdp-cabin {fc}->{tc} {d}: {r} taps={t}".format(
                fc=fc, tc=tc, d=d,
                r=(rows[0]["flight_no"] if rows else "no-data"),
                t=",".join(str(x) for x in taps)))
        return n
    except Exception as e:
        if log:
            log("cdp-cabin {fc}->{tc} {d}: ERR {c}: {m}".format(
                fc=fc, tc=tc, d=d, c=type(e).__name__,
                m=str(e)[:120]))
        # a dead renderer/session must not poison the rest of
        # the batch - reconnect and continue.
        try:
            cdp.connect()
            cdp.sess = cdp.rpc("Target.attachToTarget",
                               {"targetId": cdp.tid,
                                "flatten": True})["sessionId"]
        except Exception:
            pass
        return 0


def capture_batch(net_cfg, data_dir, targets, log=None,
                  wait_s=12.0, home_s=4.0, rows_sink=None):
    """targets: [{from_city, to_city, date, cabin?, cache_id?,
    tax?}]. One browser serves the whole batch (launch cost
    dominates). Returns n_dates_stored; rows_sink optionally
    collects every captured row (economy day boards carry the
    whole flight list, not just the cheapest card)."""
    exe = find_browser()
    if not exe:
        return 0
    from core.point_fill import put_rows
    profile = os.path.abspath(
        os.path.join(str(data_dir), "edge_prof_cdp_cabin"))
    os.makedirs(profile, exist_ok=True)
    _seed_profile(profile)
    _kill_stale("edge_prof_cdp_cabin")
    time.sleep(1.0)
    proc = subprocess.Popen(
        [exe, "--user-data-dir=" + profile,
         "--remote-debugging-port=" + str(PORT),
         "--no-first-run", "--no-default-browser-check",
         "--window-size=420,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stored = 0
    cdp = None
    try:
        bws = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/json/version" % PORT,
                        timeout=2) as r:
                    bws = json.loads(r.read().decode())[
                        "webSocketDebuggerUrl"]
                break
            except Exception:
                time.sleep(0.5)
        if not bws:
            raise RuntimeError("debug endpoint never opened")
        cdp = _CDP(bws)
        cdp.connect()
        # one warm tab: the touch home sets the cookies/referer that
        # keep the list deep link out of the login wall (verified).
        cdp.open_tab("https://m.flight.qunar.com/")
        time.sleep(home_s)
        for t in targets:
            fc = str(t.get("from_city") or "").strip()
            tc = str(t.get("to_city") or "").strip()
            d = str(t.get("date") or "").strip()
            if not (fc and tc and d):
                continue
            stored += _capture_target(
                cdp, fc, tc, d, t.get("cabin") or "business",
                data_dir, log=log, wait_s=wait_s,
                rows_sink=rows_sink, cache_id=t.get("cache_id"),
                tax=float(t.get("tax") or 0.0))
    finally:
        if cdp and cdp.ws:
            try:
                cdp.ws.close()
            except Exception:
                pass
        _tree_kill(proc)
    return stored


def capture_day(net_cfg, data_dir, from_city, to_city, date,
                route_id, log=None, tax=0.0, cabin=""):
    """v1.31: ONE economy date through the real browser - the day
    detail's '查当日真实班次' button. Mines the whole visible card
    list (exact dep/arr + pay price per flight), deposits the lowest
    row into the route's point-fill bucket (merge_point_fill then
    promotes reference-only days) and queues every timed row for the
    schedule board. Returns {rows, stored, queued}."""
    from core.point_fill import queue_sched_deposit
    cab = str(cabin or "").strip().lower()
    if cab not in ("business", "first"):
        cab = ""
    bucket = ("cdp-cabin-{fc}-{tc}".format(
        fc=from_city, tc=to_city) if cab else route_id)
    sink = []
    stored = capture_batch(
        net_cfg, data_dir,
        [{"from_city": from_city, "to_city": to_city, "date": date,
          "cabin": cab, "cache_id": bucket, "tax": tax}],
        log=log, rows_sink=sink, wait_s=25.0)
    queued = queue_sched_deposit(data_dir, sink)
    rows = [{"flight_no": str(r.get("flight_no") or ""),
             "dep_time": str(r.get("dep_time") or ""),
             "arr_time": str(r.get("arr_time") or ""),
             "total": r.get("total")} for r in sink]
    rows.sort(key=lambda r: (r["dep_time"], float(r["total"] or 0)))
    return {"rows": rows, "stored": stored, "queued": queued}


def patrol_fill(cw, routes, data_dir, log=None, throttle_hits=0):
    """v1.27 patrol hook: bounded real-browser capture. Fires when the
    booking gateway is throttled (n_thr > 0) or every 4th round so
    precision data keeps landing even while the gateway works. The
    daily cap (default 12 dates) bounds the browser minutes; deposits
    land in the point-fill cache and absorb on the NEXT round's point
    pass. Returns an info dict for /api/cabin."""
    if cw is not None and not cw.get("cdp_capture", True):
        return {"skipped": "disabled"}
    led_path = os.path.join(str(data_dir), "cdp_cabin_ledger.json")
    led = {}
    try:
        with open(led_path, encoding="utf-8") as f:
            led = json.load(f)
    except Exception:
        led = {}
    rnd = int(led.get("rounds") or 0) + 1
    led["rounds"] = rnd
    today = dt.date.today().isoformat()
    days = led.setdefault("days", {})
    used = int(days.get(today) or 0)
    cap = int((cw or {}).get("cdp_capture_daily_cap") or 24)
    info = {"round": rnd, "used": used, "cap": cap}

    def _flush():
        try:
            tmp = led_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(led, f, ensure_ascii=False)
            os.replace(tmp, led_path)
        except Exception:
            pass

    # v1.30: every-2nd-round cadence (was 4th) - precision gaps now
    # far outnumber time gaps, and the daily cap is the real bound.
    if throttle_hits <= 0 and (rnd % 2) != 1:
        _flush()
        info["skipped"] = "cadence"
        return info
    if used >= cap:
        _flush()
        info["skipped"] = "daily-cap"
        return info
    from .cabin_monitor import (patrol_legs, precision_gap_dates,
                                time_gap_dates)
    from .cabin_monitor import load_history as _cabin_history_load
    hist = _cabin_history_load(data_dir)
    legs = patrol_legs(cw or {}, routes or [])
    k = int((cw or {}).get("cdp_dates_per_round") or 4)
    d_from = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    d_to = (dt.date.today() + dt.timedelta(days=60)).isoformat()
    targets = []
    for leg in legs:
        hid = "leg-{fc}-{tc}".format(fc=leg["from_city"],
                                        tc=leg["to_city"])
        # v1.32: time gaps keep priority, then PRECISION gaps
        # (booking-only dates) fill the budget - the patrol used
        # to sleep on 'no-gaps' while 30+ days per leg still ran
        # on estimates alone.
        got = time_gap_dates(hist or {}, hid, d_from, d_to)[:k]
        have = set(got)
        for g in precision_gap_dates(hist or {}, hid, d_from, d_to):
            if len(got) >= k:
                break
            if g not in have:
                got.append(g)
                have.add(g)
        for g in got:
            targets.append({"from_city": leg["from_city"],
                            "to_city": leg["to_city"], "date": g})
    if not targets:
        _flush()
        info["skipped"] = "no-gaps"
        return info
    targets = targets[:max(0, cap - used)]
    stored = capture_batch({}, data_dir, targets,
                           log=(lambda m: log.info(str(m))
                                if log else None))
    days[today] = used + len(targets)
    _flush()
    info.update({"targets": len(targets), "stored": stored})
    return info
