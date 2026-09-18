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


def capture_batch(net_cfg, data_dir, targets, log=None,
                  wait_s=12.0, home_s=4.0):
    """targets: [{from_city, to_city, date}]. One browser serves the
    whole batch (launch cost dominates). Returns n_dates_stored."""
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
            try:
                cdp.nav(list_url(fc, tc, d))
                time.sleep(4.0)
                wall = cdp.ev("location.href")
                if wall and "login" in str(wall):
                    if log:
                        log("cdp-cabin {fc}->{tc} {d}: login-wall "
                            "(warm the profile once in a real "
                            "browser)".format(fc=fc, tc=tc, d=d))
                    continue
                taps = [cdp.ev(TAP_FILTER_JS)]
                time.sleep(2.0)
                taps.append(cdp.ev(TAP_CABIN_ROW_JS))
                time.sleep(1.5)
                taps.append(cdp.ev(TAP_BIZ_JS))
                time.sleep(1.5)
                taps.append(cdp.ev(TAP_BIZ_JS) if False else
                            cdp.ev(TAP_CONFIRM_JS))
                # poll: the post-confirm re-render races a single
                # evaluate (renderer swap can null it) - mine on the
                # same cadence the recon verified.
                best = None
                deadline = time.time() + max(6.0, wait_s)
                while time.time() < deadline:
                    time.sleep(2.0)
                    best = cdp.ev(MINER_JS)
                    if best and best.get("p") and best.get("no"):
                        break
                if best and best.get("p") and best.get("no"):
                    cache, n = put_rows(
                        data_dir, "cdp-cabin-{fc}-{tc}".format(
                            fc=fc, tc=tc),
                        [{"date": d, "total": best["p"],
                          "flight_no": best["no"],
                          "dep_time": best.get("dep") or "",
                          "arr_time": best.get("arr") or "",
                          "cabin": "business",
                          "from_city": fc, "to_city": tc}],
                        tax=float(t.get("tax") or 0.0))
                    stored += n
                if log:
                    log("cdp-cabin {fc}->{tc} {d}: {r} taps={t}".format(
                        fc=fc, tc=tc, d=d,
                        r=(best or {}).get("no") or "no-data",
                        t=",".join(str(x) for x in taps)))
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
    finally:
        if cdp and cdp.ws:
            try:
                cdp.ws.close()
            except Exception:
                pass
        _tree_kill(proc)
    return stored


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
    from .cabin_monitor import patrol_legs, time_gap_dates
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
        for g in time_gap_dates(hist or {}, hid, d_from, d_to)[:k]:
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
