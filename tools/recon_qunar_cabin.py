# -*- coding: utf-8 -*-
"""v1.27 recon: mine qunar touch flight-list cards (flight no, dep/
arr times, price) with a REAL headed browser via CDP - the same
pipeline the production cdp_board uses. Verified live 2026-09-17:
touch list + warm-home loads 200+ cards; tap-biz flips the cabin.
Pure recon: no POSTs, only writes data/recon_qunar_cabin.json.

Usage (repo root):
  python -Xutf8 tools/recon_qunar_cabin.py --site touch --warm-home \
      --tap-biz --from 北京 --to 上海 --date 2026-09-19 --wait 12
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "recon_qunar_cabin.json")
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
    os.path.expandvars("%LocalAppData%\\Google\\Chrome"
                      "\\Application\\chrome.exe"),
)

TAP_FILTER_JS = ("(function(){var all="
          "document.querySelectorAll('div,span,li,section,a,button');"
          "for(var i=0;i<all.length;i++){"
          "var t=(all[i].textContent||'').trim();"
          "if(t==='\u7b5b\u9009'){all[i].click();"
          "return 'filter-opened';}}"
          "return 'filter-not-found';})()")

TAP_BIZ_JS = ("(function(){var hits=[];var all="
          "document.querySelectorAll('div,span,li,section,a,button,label');"
          "for(var i=0;i<all.length;i++){"
          "var t=(all[i].textContent||'').trim();"
          "if(t&&t.length<=12&&t.indexOf('\u516c\u52a1')>=0){"
          "hits.push(all[i]);}}"
          "if(hits.length){hits[hits.length-1].click();"
          "return 'biz-tapped:'+hits.length;}"
          "var cab=[];var seen={};"
          "for(var j=0;j<all.length;j++){"
          "var s=(all[j].textContent||'').trim();"
          "if(s&&s.length<=10&&s.indexOf('\u8231')>=0&&!seen[s]){"
          "seen[s]=1;cab.push(s);}}"
          "return 'biz-chip-not-found;cabin-texts:'+cab.join('|');})()")

TAP_CABIN_ROW_JS = ("(function(){var all="
          "document.querySelectorAll('div,span,li,section,a,button,label');"
          "for(var i=0;i<all.length;i++){"
          "var t=(all[i].textContent||'').trim();"
          "if(t==='\u8231\u4f4d'){all[i].click();"
          "return 'cabin-row-opened';}}"
          "return 'cabin-row-not-found';})()")

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
var cards={},pnodes=document.querySelectorAll("[class*=price]");
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
var f=fm[1]+fm[2];
if(!cards[f]||pp<cards[f].p){cards[f]={p:pp,dep:ts[0]||"",arr:ts[1]||"",biz:/公务|商务/.test(ct)};}}
var rows=[];
for(var k in cards){rows.push({no:k,p:cards[k].p,dep:cards[k].dep,arr:cards[k].arr,biz:cards[k].biz});}
rows.sort(function(a,b){return a.p-b.p;});
var txt=document.body.innerText||"";
var samples=[],seen=0,pn2=document.querySelectorAll("[class*=price]");
for(var j=0;j<pn2.length&&seen<3;j++){
var c2=cardOf(pn2[j]);
if(!c2){continue;}
var s2=(c2.innerText||"").replace(/\\s+/g," ").slice(0,220);
if(s2){samples.push(s2);seen++;}}
return {title:document.title||"",final_url:location.href.slice(0,200),
text_len:txt.length,n_price_nodes:pnodes.length,n_cards:rows.length,
has_biz_word:/公务|商务|头等/.test(txt),rows:rows.slice(0,8),
card_samples:samples,
biz_hits:(txt.match(/.{0,20}(公务|商务|头等).{0,40}/g)||[]).slice(0,6)};
})()
"""


def list_url(site, fc, tc, date):
    from core.cities import CITIES
    py = {c["name"]: (c.get("pinyin") or "") for c in CITIES}
    if site == "ctrip":
        return ("https://flights.ctrip.com/online/list/oneway-"
                + py.get(fc, fc) + "-" + py.get(tc, tc)
                + "?depdate=" + date)
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


def kill_stale(profile_name):
    """Kill leftover browser processes holding the debug port / the
    recon profile (proc.kill() only reaps the launcher, children
    survive and block the next run)."""
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'"
         " -or Name='chrome.exe'\" | Where-Object {$_.CommandLine"
         " -match '" + profile_name + "'} | ForEach-Object {"
         " Stop-Process -Id $_.ProcessId -Force }"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=20)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=("touch", "ctrip"),
                    default="touch")
    ap.add_argument("--from", dest="fc", default="北京")
    ap.add_argument("--to", dest="tc", default="上海")
    ap.add_argument("--date", default="2026-09-19")
    ap.add_argument("--wait", type=float, default=12.0)
    ap.add_argument("--profile-dir", default="edge_prof_recon_warm")
    ap.add_argument("--warm-home", action="store_true")
    ap.add_argument("--tap-biz", action="store_true")
    args = ap.parse_args()

    import websocket

    exe = find_browser()
    if not exe:
        print("no chrome/edge binary found")
        return 2
    profile = os.path.join(BASE, "data", args.profile_dir)
    os.makedirs(profile, exist_ok=True)
    kill_stale(args.profile_dir)
    time.sleep(1.0)
    url = list_url(args.site, args.fc, args.tc, args.date)
    print("URL:", url)
    proc = subprocess.Popen(
        [exe, "--user-data-dir=" + profile,
         "--remote-debugging-port=" + str(PORT),
         "--no-first-run", "--no-default-browser-check",
         "--window-size=420,900", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = {"site": args.site, "url": url, "ok": False}
    ws = None
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

        state = {"ws": None, "sess": None}

        def connect():
            w = websocket.create_connection(bws, timeout=15,
                                            suppress_origin=True)
            state["ws"] = w
            return w

        ws = connect()

        def rpc(method, params=None, mid=990):
            w = state["ws"]
            w.send(json.dumps({"id": mid, "method": method,
                               "params": params or {}}))
            while True:
                m = json.loads(w.recv())
                if m.get("id") == mid:
                    break
            if m.get("error"):
                raise RuntimeError(str(m["error"])[:200])
            return m.get("result")

        tid = rpc("Target.createTarget",
                  {"url": "about:blank"})["targetId"]
        state["sess"] = rpc("Target.attachToTarget",
                            {"targetId": tid,
                             "flatten": True})["sessionId"]

        def nav(u, mid=988):
            w = state["ws"]
            w.send(json.dumps({"id": mid, "method": "Page.navigate",
                               "params": {"url": u},
                               "sessionId": state["sess"]}))
            while True:
                m = json.loads(w.recv())
                if m.get("id") == mid:
                    break

        def ev(expr, mid=991):
            for attempt in (0, 1):
                try:
                    w = state["ws"]
                    w.send(json.dumps({
                        "id": mid, "method": "Runtime.evaluate",
                        "params": {"expression": expr,
                                   "returnByValue": True},
                        "sessionId": state["sess"]}))
                    while True:
                        m = json.loads(w.recv())
                        if m.get("id") == mid:
                            break
                    return (((m.get("result") or {}).get("result") or {})
                            .get("value"))
                except Exception:
                    if attempt:
                        raise
                    time.sleep(1.2)
                    try:
                        state["ws"].close()
                    except Exception:
                        pass
                    connect()
                    state["sess"] = rpc(
                        "Target.attachToTarget",
                        {"targetId": tid,
                         "flatten": True})["sessionId"]

        if args.warm_home:
            nav("https://m.flight.qunar.com/")
            time.sleep(4.0)
        nav(url)
        if args.tap_biz:
            time.sleep(4.0)
            result["tap_filter"] = ev(TAP_FILTER_JS)
            time.sleep(2.0)
            result["tap_cabin"] = ev(TAP_CABIN_ROW_JS)
            time.sleep(1.5)
            result["tap_biz"] = ev(TAP_BIZ_JS)
            time.sleep(1.5)
            result["tap_confirm"] = ev(TAP_CONFIRM_JS)
            time.sleep(10.0)

        deadline = time.time() + max(8.0, args.wait)
        best = None
        while time.time() < deadline:
            time.sleep(2.0)
            snap = ev(MINER_JS)
            if not snap:
                continue
            best = snap
            if snap.get("n_cards") and (
                    not args.tap_biz or snap.get("has_biz_word")):
                break
        if best:
            result.update(best)
            result["ok"] = bool(best.get("n_cards"))
    except Exception as e:
        result["error"] = type(e).__name__ + ": " + str(e)[:300]
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID",
                            str(proc.pid)],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=15)
        except Exception:
            pass
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False, indent=1)[:2800])
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
