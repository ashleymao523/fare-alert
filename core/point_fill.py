# -*- coding: utf-8 -*-
# v0.76: 精点补查缓存 (point-fill cache).
#
# Recon conclusions (2026-09-14, evidence in tools/point_probe.py):
# - qunar low-price calendar leaves dates unpriced server-side; those
#   dates are NOT sold out and NOT a crawler bug - the gateway just has
#   no cached floor price yet.
# - the per-date list API (touchInnerList) is Bella-signed + fingerprint
#   gated: plain POSTs, headless dumps and an embedded real browser all
#   get the same uniform 1999 rejection -> no keyless automated point
#   query today.
#
# Gap dates therefore fill via two tracks:
#   track A (auto):  Amadeus per-date offers (_cached_fill_offers).
#   track B (cache): THIS module - point-queried rows captured in a real
#     browser (bookmarklet / agent / manual) persist here with a TTL and
#     replay over reference-only rows on every crawl. Real rows win.
from __future__ import annotations

import datetime as _dt
import json
import os
import time

CACHE_NAME = "point_fill_cache.json"
DEPOSIT_NAME = "sched_deposit.json"   # v0.83: board-teaching queue
POINT_TTL = 48 * 3600          # captured price stays fresh for 2 days
POINT_SOURCE = "point-fill"
MAX_ROWS_PER_ROUTE = 400       # 60d window x out+ret: huge headroom


def cache_path(data_dir):
    return os.path.join(data_dir, CACHE_NAME)


def deposit_path(data_dir):
    return os.path.join(data_dir, DEPOSIT_NAME)


def load_cache(data_dir):
    try:
        with open(cache_path(data_dir), encoding="utf-8") as f:
            cache = json.load(f)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


def _atomic_write(path, obj):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _fresh_ts(entry, now):
    try:
        return (now - float(entry.get("ts") or 0)) <= POINT_TTL
    except Exception:
        return False


def fresh_entries(cache, route_id, now=None):
    """{date: entry} for one route, TTL-filtered, bad rows dropped."""
    now = now if now is not None else time.time()
    out = {}
    for d, e in ((cache.get(route_id) or {}).items()):
        if not isinstance(e, dict):
            continue
        try:
            _dt.date.fromisoformat(str(d))
            if float(e.get("bare")) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        if _fresh_ts(e, now):
            out[str(d)] = e
    return out
def put_rows(data_dir, route_id, rows, tax=0.0, now=None):
    """Persist captured rows. Each row: {date, total, flight_no?,
    dep_time?, arr_time?}; total is the pay price (tax included).
    Stored as bare (total - tax) to keep total_price() semantics.
    Returns (cache, n_stored); invalid rows are skipped, not fatal."""
    now = now if now is not None else time.time()
    cache = load_cache(data_dir)
    bucket = cache.setdefault(route_id, {}) if isinstance(cache, dict) else {}
    n = 0
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        d = str(r.get("date") or "").strip()
        try:
            _dt.date.fromisoformat(d)
            total = float(r.get("total"))
        except (TypeError, ValueError):
            continue
        if total <= 0:
            continue
        bucket[d] = {
            "bare": round(total - float(tax or 0), 1),
            "total": round(total, 1),
            "flight_no": str(r.get("flight_no") or "").strip(),
            "dep_time": str(r.get("dep_time") or "").strip()[:5],
            "arr_time": str(r.get("arr_time") or "").strip()[:5],
            # v0.83: cabin tag + city pair so the business watch and the
            # board deposit can consume the same captured row.
            "cabin": (str(r.get("cabin") or "").strip().lower()
                      if str(r.get("cabin") or "").strip().lower()
                      in ("business", "first") else ""),
            "from_city": str(r.get("from_city") or "").strip()[:24],
            "to_city": str(r.get("to_city") or "").strip()[:24],
            "ts": now,
        }
        n += 1
    if len(bucket) > MAX_ROWS_PER_ROUTE:
        keep = sorted(bucket.items(), key=lambda kv: kv[1].get("ts", 0))
        cache[route_id] = dict(keep[-MAX_ROWS_PER_ROUTE:])
    _atomic_write(cache_path(data_dir), cache)
    return cache, n


def queue_sched_deposit(data_dir, rows):
    """v0.83: queue real-browser captured schedule rows for the board.

    Rows with a flight number AND at least one time land in a queue
    file; the worker's next update_sched_db absorbs them into the
    persistent flight-schedule db under the row's own weekday. One
    point-queried Sunday flight therefore teaches the board Sunday
    departures - closing dow holes the board API can never fetch on
    demand (it only ever returns today+tomorrow rows). Returns the
    number of queued rows; invalid rows are skipped, never fatal."""
    want = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        no = str(r.get("flight_no") or "").strip().upper()
        dep = str(r.get("dep_time") or "").strip()[:5]
        arr = str(r.get("arr_time") or "").strip()[:5]
        try:
            d = _dt.date.fromisoformat(str(r.get("date") or "").strip())
        except ValueError:
            continue
        if no and (dep or arr):
            want.append({"no": no, "date": d.isoformat(),
                         "dep": dep, "arr": arr,
                         "from": str(r.get("from_city") or "").strip()[:24],
                         "to": str(r.get("to_city") or "").strip()[:24],
                         "ts": time.time()})
    if not want:
        return 0
    try:
        with open(deposit_path(data_dir), encoding="utf-8") as f:
            q = json.load(f)
        q = q if isinstance(q, list) else []
    except Exception:
        q = []
    q.extend(want)
    if len(q) > 4000:            # ring cap: the queue drains every cycle
        q = q[-4000:]
    _atomic_write(deposit_path(data_dir), q)
    return len(want)


# v0.79: bookmarklet that runs ON the qunar flight-list page, mines the
# cheapest price straight out of the rendered DOM and fires a no-cors
# POST back to the panel. __FA_ORIGIN__ is swapped at generation time
# (request.host_url), so a phone Safari copying it from the LAN URL
# posts to the desktop box, not to 127.0.0.1.
_BOOKMARKLET_TEMPLATE = r"""(function(){
var ORIGIN="__FA_ORIGIN__";
var CABIN="__FA_CABIN__";
var q={};
location.search.replace(/[?&]([^=&]+)=([^&]*)/g,function(_,k,v){q[k]=decodeURIComponent(v);});
var from=q.depCity||"",to=q.arrCity||"",date=q.goDate||"";
function toast(msg,ok){
var t=document.createElement("div");
t.textContent=msg;
t.style.cssText="position:fixed;z-index:99999;right:12px;bottom:12px;background:"+(ok?"#0a8554":"#c0392b")+";color:#fff;padding:10px 14px;border-radius:8px;font:13px/1.4 -apple-system,sans-serif;max-width:80vw;box-shadow:0 4px 14px rgba(0,0,0,.25)";
document.body.appendChild(t);
setTimeout(function(){t.remove();},3500);
}
if(!from||!to||!date){toast("这不是去哪儿航班列表页(缺城市/日期参数)",false);return;}
var prices=[],nodes=document.querySelectorAll("[class*=price]");
for(var i=0;i<nodes.length;i++){
var m=(nodes[i].textContent||"").replace(/[,\uFF0C\s]/g,"").match(/(?:\u00A5|\uFFE5)?(\d{2,5})/);
if(m){var p=parseInt(m[1],10);if(p>=50&&p<=99999)prices.push(p);}
}
var best=prices.length?Math.min.apply(null,prices):0;
if(!best){
var inp=prompt("未抓到价格, 请输入 "+from+"-"+to+" "+date+" 最低含税总价(数字):");
if(!inp)return;
best=parseInt(inp.replace(/[^\d]/g,""),10);
if(!best){toast("无效价格",false);return;}
}
var txt=document.body.innerText||"";
var fm=txt.match(/([A-Z][A-Z0-9])\s?(\d{3,4})/);
var fno=fm?fm[1]+fm[2]:"";
var tm=txt.match(/(?:^|[^\d])(\d{1,2}:\d{2})(?=[^\d]|$)/g)||[];
var dep=tm.length?tm[0].match(/\d{1,2}:\d{2}/)[0]:"";
var arr=tm.length>1?tm[1].match(/\d{1,2}:\d{2}/)[0]:"";
var body=JSON.stringify({from_city:from,to_city:to,cabin:CABIN,rows:[{date:date,total:best,flight_no:fno,dep_time:dep,arr_time:arr}]});
fetch(ORIGIN+"/api/point-fill",{method:"POST",headers:{"Content-Type":"text/plain"},body:body,mode:"no-cors"})
.then(function(){toast("已回填 "+from+"-"+to+" "+date+" \u00A5"+best+" (含航班号/时刻则一并带上, 面板已热更新)",true);})
.catch(function(){toast("回填失败: 面板不可达 "+ORIGIN,false);});
})();"""


def build_bookmarklet(origin, cabin=""):
    """v0.79: full javascript: URL bound to one panel origin.

    v0.83: cabin="" keeps the economy bookmark; "business"/"first"
    tags every captured row so the business watch can absorb real
    cabin prices captured on a cabin-filtered qunar page - no API
    key involved."""
    cab = str(cabin or "").strip().lower()
    if cab not in ("business", "first"):
        cab = ""
    return "javascript:" + _BOOKMARKLET_TEMPLATE.replace(
        "__FA_ORIGIN__", str(origin).rstrip("/")).replace(
        "__FA_CABIN__", cab)


def merge_point_fill(deals, cache, route_id, now=None):
    """Replace reference-only rows (interp/nearby-ref) with fresh
    point-fill rows. Real rows (qunar/amadeus/point) always win.
    Returns (deals, n_replaced); output sorted by (price, date)."""
    from .flights import NON_REAL_SOURCES
    from .models import FlightDeal
    entries = fresh_entries(cache, route_id, now)
    if not entries:
        return deals, 0
    out, replaced = [], 0
    for d in deals:
        e = entries.get(d.date)
        if e and getattr(d, "source", "") in NON_REAL_SOURCES:
            out.append(FlightDeal(
                date=d.date,
                bare_price=float(e["bare"]),
                flight_no=e.get("flight_no") or "",
                dep_time=e.get("dep_time") or "",
                arr_time=e.get("arr_time") or "",
                duration_text=d.duration_text,
                time_src=POINT_SOURCE,
                dep_src=POINT_SOURCE,
                arr_src=POINT_SOURCE,
                source=POINT_SOURCE,
                url=d.url,
            ))
            replaced += 1
        else:
            out.append(d)
    if replaced:
        out.sort(key=lambda x: (x.bare_price, x.date))
    return out, replaced


def patch_snapshot_deals(deals, cache, route_id, now=None):
    """Dict-row twin of merge_point_fill for the live snapshot: lets
    POST /api/point-fill reflect in the UI immediately, before the
    next crawl replays the same cache. Returns n_replaced."""
    entries = fresh_entries(cache, route_id, now)
    n = 0
    for d in deals or []:
        if not isinstance(d, dict):
            continue
        e = entries.get(str(d.get("date") or ""))
        # v0.87: booking-ref also yields to a captured real OTA price.
        if e and d.get("source") in ("interp", "nearby-ref",
                                     "booking-ref"):
            d["bare_price"] = float(e["bare"])
            d["total_price"] = float(e.get("total") or e["bare"])
            d["source"] = POINT_SOURCE
            if e.get("flight_no"):
                d["flight_no"] = e["flight_no"]
            for k in ("dep_time", "arr_time"):
                if e.get(k):
                    d[k] = e[k]
            for k in ("time_src", "dep_src", "arr_src"):
                d[k] = POINT_SOURCE
            d["ref_offset"] = 0
            n += 1
    return n


def gap_dates(deals, window):
    """Dates still carrying reference-only prices -> capture targets.
    window is [date_from, date_to]; deals are raw snapshot dicts."""
    have_real = {str(d.get("date")) for d in deals or []
                 if d.get("source") not in ("interp", "nearby-ref")}
    out = []
    try:
        cur = _dt.date.fromisoformat(window[0])
        end = _dt.date.fromisoformat(window[1])
    except (TypeError, ValueError):
        return out
    while cur <= end:
        iso = cur.isoformat()
        if iso not in have_real:
            out.append(iso)
        cur += _dt.timedelta(days=1)
    return out
