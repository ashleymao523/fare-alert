# -*- coding: utf-8 -*-
"""FareAlert MCP Server (stdio, newline-delimited JSON-RPC 2.0).

零第三方依赖的最小 MCP 实现:initialize / tools/list / tools/call。
五个工具复用 core 层既有函数,遵守 AGENTS.md 红线(只读查询、低频、
watch_* 写 config 前自动备份)。启动: python mcp_server.py
"""
import datetime as dt
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stdin.reconfigure(encoding="utf-8", errors="replace")

from core.config import load_config, save_config
from core.intent import parse_intent, window_from_date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SNAPSHOT_PATH = os.path.join(BASE_DIR, "data", "snapshot.json")
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "fare-alert", "version": "0.11"}


def _err(msg):
    return {"content": [{"type": "text", "text": "ERROR: " + msg}], "isError": True}


def _ok(text):
    return {"content": [{"type": "text", "text": text}]}


TOOLS = [
    {
        "name": "fare_search",
        "description": "查未来N天某航线的含税最低机票价(总价=裸价+机建+燃油),返回最低价TOP列表",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_city": {"type": "string", "description": "出发城市中文名,如 杭州"},
                "to_city": {"type": "string", "description": "到达城市中文名,如 重庆"},
                "days": {"type": "integer", "description": "查询未来天数,默认14,上限60", "default": 14},
            },
            "required": ["from_city", "to_city"],
        },
    },
    {
        "name": "train_search",
        "description": "查某日期 12306 车次与全席位票价(含卧铺/二等座,供对比)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_station": {"type": "string", "description": "出发站,如 杭州东"},
                "to_station": {"type": "string", "description": "到达站,如 重庆北"},
                "date": {"type": "string", "description": "YYYY-MM-DD,默认明天"},
            },
            "required": ["from_station", "to_station"],
        },
    },
    {
        "name": "watch_add",
        "description": "一句话新增监控线路,如 '五一杭州飞成都800以内'。写入前自动备份 config.json",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "自然语言描述(城市对+阈值+日期均可选)"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "watch_del",
        "description": "按 route_id 删除一条监控线路(删除前自动备份 config.json)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "route_id": {"type": "string", "description": "线路ID,如 hangzhou-chongqing"},
            },
            "required": ["route_id"],
        },
    },
    {
        "name": "snapshot_get",
        "description": "读最新监控快照:每条线路的最低真实含税价/触发日/数据源(估算价不计入)",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _backup_config():
    if os.path.exists(CONFIG_PATH):
        shutil.copy2(CONFIG_PATH, CONFIG_PATH + ".bak")


def tool_fare_search(args):
    import requests
    from core.alerts import total_price
    from core.flights import booking_url, fetch_calendar, window_dates
    cfg = load_config(CONFIG_PATH)
    days = max(1, min(int(args.get("days") or 14), 60))
    d0 = dt.date.today() + dt.timedelta(days=1)
    dates = window_dates(d0.isoformat(), (d0 + dt.timedelta(days=days - 1)).isoformat())
    sess = requests.Session()
    deals = fetch_calendar(sess, cfg["network"], args["from_city"], args["to_city"],
                           dates[0], dates[-1]) or []
    if not deals:
        return _ok("未取到 %s->%s 未来%d天日历价(数据源可能限流,稍后再试)"
                   % (args["from_city"], args["to_city"], days))
    rows = sorted(((total_price(d.bare_price, cfg["tax"]), d.date) for d in deals
                   if d.bare_price), key=lambda x: x[0])[:10]
    lines = ["%s->%s 未来%d天 含税最低TOP10:" % (args["from_city"], args["to_city"], days)]
    for total, date in rows:
        lines.append("  %s  ¥%d  购票:%s" % (date, total,
                    booking_url(args["from_city"], args["to_city"], date)))
    return _ok("\n".join(lines))


def tool_train_search(args):
    import requests
    from core.trains import get_stations, query_pair
    cfg = load_config(CONFIG_PATH)
    date = args.get("date") or (dt.date.today() + dt.timedelta(days=1)).isoformat()
    sess = requests.Session()
    stations = get_stations(sess, cfg["network"],
                            os.path.join(BASE_DIR, "data", "train_cache.json"))
    fares = query_pair(sess, cfg["network"], date,
                       args["from_station"], args["to_station"], stations) or []
    if not fares:
        return _ok("%s->%s %s 未查到车次(可能无直达或车站名有误)"
                   % (args["from_station"], args["to_station"], date))
    lines = ["%s->%s %s 车次(%d趟):" % (args["from_station"], args["to_station"],
                                        date, len(fares))]
    for f in fares[:15]:
        seats = " ".join("%s¥%s" % (k, v) for k, v in list(f.seats.items())[:4])
        lines.append("  %s %s-%s %s %s" % (f.train_code, f.dep_time, f.arr_time,
                                           f.duration_text, seats))
    return _ok("\n".join(lines))


def tool_watch_add(args):
    r = parse_intent(args["text"])
    if not r["ok"]:
        return _err("解析失败: " + "; ".join(r["ambiguous"]))
    cfg = load_config(CONFIG_PATH)
    rid = r["route_id"]
    if any(x.get("id") == rid for x in cfg["routes"]):
        return _ok("线路 %s 已存在,未改动。如需修改先 watch_del 再添加。" % rid)
    route = {
        "id": rid, "from_city": r["from_city"], "to_city": r["to_city"],
        "window_days": r["window_days"],
        "threshold_total": r["threshold_total"] if r["threshold_total"] is not None else 500,
        "trip_type": r["trip_type"], "intl": r["intl"],
        "from_iata": "", "to_iata": "",
        "train_compare": {"enabled": False, "station_pairs": []},
    }
    if r["date_from"]:
        route["window_days"] = window_from_date(r)
    _backup_config()
    cfg["routes"].append(route)
    save_config(CONFIG_PATH, cfg)
    note = "; ".join(r["ambiguous"]) or "完整解析"
    return _ok("已添加监控 %s->%s (id=%s, 阈值¥%d, 未来%d天)。提示: %s\n"
               "下一轮询周期生效;网页端可再调阈值/对比车次。"
               % (r["from_city"], r["to_city"], rid,
                  route["threshold_total"], route["window_days"], note))


def tool_watch_del(args):
    cfg = load_config(CONFIG_PATH)
    before = len(cfg["routes"])
    cfg["routes"] = [x for x in cfg["routes"] if x.get("id") != args["route_id"]]
    if len(cfg["routes"]) == before:
        return _err("未找到 route_id=%s(用 snapshot_get 查现有线路)" % args["route_id"])
    _backup_config()
    save_config(CONFIG_PATH, cfg)
    return _ok("已删除 %s(现存%d条线路)" % (args["route_id"], len(cfg["routes"])))


def tool_snapshot_get(args):
    if not os.path.exists(SNAPSHOT_PATH):
        return _ok("暂无快照(监控主循环尚未跑过一轮)")
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        snap = json.load(f)
    lines = []
    for rt in snap.get("routes", []):
        deals = [d for d in (rt.get("deals") or [])
                 if d.get("total_price") and d.get("source") not in ("nearby-ref", "interp")]
        if deals:
            best = min(deals, key=lambda d: d["total_price"])
            lines.append("%s->%s(id=%s) 最低真实含税 ¥%d @%s [%s]"
                         % (rt.get("from_city"), rt.get("to_city"), rt.get("id"),
                            best["total_price"], best["date"], best.get("source")))
        else:
            lines.append("%s->%s(id=%s) 暂无真实价" %
                         (rt.get("from_city"), rt.get("to_city"), rt.get("id")))
    try:  # M2: surface degraded sources so an agent can self-serve diagnosis
        from core.health import SourceHealth
        hh = SourceHealth(os.path.join(BASE_DIR, "data", "health.json"))
        lines.extend(_degraded_lines(hh))
    except Exception:
        pass
    return _ok("\n".join(lines) or "快照为空")


def _degraded_lines(hh):
    out = []
    for s in hh.snapshot()["sources"]:
        if s["degraded"] or s["consecutive_fails"]:
            rep = hh.diagnose(s["source"])
            causes = "; ".join(c["cause"] for c in rep["candidates"]) or "未知"
            out.append("⚠ 数据源 %s 已降级(连续失败%d) 原因: %s" %
                       (s["source"], s["consecutive_fails"], causes))
    return out


HANDLERS = {"fare_search": tool_fare_search, "train_search": tool_train_search,
            "watch_add": tool_watch_add, "watch_del": tool_watch_del,
            "snapshot_get": tool_snapshot_get}


def handle(msg):
    # notifications (no id) must never be replied to nor executed
    if msg.get("id") is None:
        return None
    if msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return {"jsonrpc": "2.0", "id": msg.get("id"),
                "error": {"code": -32600, "message": "invalid request"}}
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        fn = HANDLERS.get(name)
        if not fn:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": "unknown tool: " + str(name)}}
        try:
            return {"jsonrpc": "2.0", "id": mid, "result": fn(params.get("arguments") or {})}
        except Exception as e:  # tool crash -> MCP isError result, not transport error
            return {"jsonrpc": "2.0", "id": mid, "result": _err(repr(e)[:200])}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": "method not found: " + str(method)}}
    return None


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            if not isinstance(msg, dict):
                resp = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32600,
                                  "message": "invalid request: batch/atomic not supported"}}
            else:
                resp = handle(msg)
        except json.JSONDecodeError as e:
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": "parse error: " + str(e)}}
        except Exception as e:  # never let one bad frame kill the session
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32603, "message": "internal error: " + repr(e)[:120]}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
