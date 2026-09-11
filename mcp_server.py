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
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stdin.reconfigure(encoding="utf-8", errors="replace")

from core.config import load_config, save_config
from core.intent import parse_intent, window_from_date

BASE_DIR = os.environ.get("FAREALERT_HOME") or os.path.dirname(
    os.path.abspath(__file__))
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
    {
        "name": "reverse_search",
        "description": "反向搜索:'¥X以内从A出发能去哪'——扫描候选目的地带,返回窗口内最低真实含税价<=预算的目的地列表(带日期/航司/直达链接/新鲜度)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_city": {"type": "string", "description": "出发城市中文名,如 杭州"},
                "budget": {"type": "number", "description": "含税总价预算(元),如 500"},
                "days": {"type": "integer", "description": "查询未来天数,默认30,上限60", "default": 30},
                "max_requests": {"type": "integer", "description": "实发请求预算,默认8,硬上限15(缓存命中不耗预算)", "default": 8},
            },
            "required": ["from_city", "budget"],
        },
    },
    {
        "name": "verify_release",
        "description": "一键跑项目验收链(单测/ui_check/前端build/面板探活), 返回 JSON 汇总(逐项 ok/耗时/尾行)。供 agent 自主验收; 默认步骤全只读, build 会重建 web/dist。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["unittest", "ui_check", "build", "health"]},
                    "description": "要跑的步骤, 默认 [unittest, ui_check, health]",
                },
            },
        },
    },
    {
        "name": "patrol_run",
        "description": "系统巡检:聚合 /api/health(快照新鲜度/worker心跳/每日自愈/板库dow覆盖) + 推送渠道就绪 + 周报计时器,产出结论并写 data/patrol_last.json。供任意 agent 或定时任务调用;notify=true 且发现异常时才经 Bark/ServerChan 推送(默认 false 不发任何通知)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "notify": {"type": "boolean",
                           "description": "发现异常时是否推送提醒,默认 false",
                           "default": False},
            },
        },
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
            state = "已降级" if s["degraded"] else "波动(尚未降级)"
            out.append("⚠ 数据源 %s %s,连续失败%d 原因: %s" %
                       (s["source"], state, s["consecutive_fails"], causes))
    return out


def tool_reverse_search(args):
    import requests
    from core.reverse import reverse_search
    cfg = load_config(CONFIG_PATH)
    days = max(1, min(int(args.get("days") or 30), 60))
    max_req = max(1, min(int(args.get("max_requests") or 8), 15))
    budget = float(args["budget"])
    today = dt.date.today()
    sess = requests.Session()
    sess.trust_env = bool(cfg.get("network", {}).get("trust_env", False))
    r = reverse_search(sess, cfg.get("network", {}), cfg.get("tax", {}),
                       args["from_city"], budget,
                       today.isoformat(),
                       (today + dt.timedelta(days=days - 1)).isoformat(),
                       max_requests=max_req,
                       data_dir=os.path.join(BASE_DIR, "data"))
    if not r["hits"]:
        return _ok("未来%d天内 %s 出发无 ≤¥%.0f 的目的地(扫描%d/候选%d,失败%d)"
                   % (days, r["from_city"], budget, r["scanned"],
                      r["pool_size"], r["failed"]))
    lines = ["%s 出发 未来%d天 ≤¥%.0f 可去(按含税总价升序):"
             % (r["from_city"], days, budget)]
    for h in r["hits"]:
        lines.append("%s ¥%d @%s %s %s%s" % (
            h["city"], h["total_price"], h["date"],
            h["airline"] or h["flight_no"], h["url"],
            " [缓存]" if h.get("cached") else ""))
    lines.append("(扫描%d/候选%d,实发请求%d,失败%d;估算价不参与)"
                 % (r["scanned"], r["pool_size"], r["requests_used"],
                    r["failed"]))
    return _ok("\n".join(lines))


def tool_verify_release(args):
    """v0.37: agent 自主验收链。每步独立超时与尾行提取, 汇总 all_ok。
    health 步骤读 config 的 webui.port 探活 /api/health(含 worker 心跳语义)。"""
    allowed = ["unittest", "ui_check", "build", "health"]
    steps = args.get("steps") or ["unittest", "ui_check", "health"]
    if isinstance(steps, str):
        steps = [steps]
    steps = [s for s in steps if s in allowed]
    if not steps:
        return _err("steps 需为 %s 的非空子集" % allowed)
    results = []
    all_ok = True
    for s in steps:
        t0 = time.time()
        try:
            if s == "health":
                port = 8765
                try:
                    cfg = load_config(CONFIG_PATH)
                    port = int((cfg.get("webui") or {}).get("port") or 8765)
                except Exception:
                    pass
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/api/health" % port, timeout=10) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                ok = bool(body.get("ok"))
                wk = body.get("worker") or {}
                wstate = ("alive" if (wk.get("ok") and wk.get("age_min", 999) < 120)
                          else ("stale" if wk else "none"))
                tail = ["ok=%s snapshot_age_min=%s worker=%s" % (
                    body.get("ok"), (body.get("snapshot") or {}).get("age_min"), wstate)]
            else:
                if s == "unittest":
                    cmd = [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests"]
                    cwd = BASE_DIR
                elif s == "ui_check":
                    cmd = [sys.executable, "-X", "utf8", "tools/ui_check.py"]
                    cwd = BASE_DIR
                else:  # build
                    npm = shutil.which("npm")
                    if not npm:
                        raise RuntimeError("npm not found on PATH")
                    cmd = [npm, "run", "build"]
                    cwd = os.path.join(BASE_DIR, "web")
                p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=300)
                ok = p.returncode == 0
                lines = [l for l in (p.stdout or "").strip().splitlines() if l.strip()]
                if s == "ui_check":
                    tail = [l for l in lines if l.startswith("FAIL")] or ["all checks passed"]
                else:
                    tail = lines[-3:]
            dur = round(time.time() - t0, 1)
        except Exception as e:
            ok = False
            dur = round(time.time() - t0, 1)
            tail = [repr(e)[:160]]
        all_ok = all_ok and ok
        results.append({"step": s, "ok": ok, "seconds": dur, "tail": tail})
    return _ok(json.dumps({"all_ok": all_ok, "steps": results}, ensure_ascii=False, indent=1))


def tool_patrol_run(args):
    """v0.40: one-shot system patrol for any agent / scheduled caller.
    Delegates to core.patrol.run_patrol (shared with the daily 09:00
    schedule) and renders the doc as readable text."""
    from core.patrol import run_patrol
    doc = run_patrol(BASE_DIR, notify=bool(args.get("notify")))
    lines = ["巡检结论: " + doc.get("verdict", "?")]
    lines += ["  [%s] %s (%s)" % (c["status"], c["name"], c["detail"])
              for c in doc.get("checks", [])]
    return _ok(json.dumps(doc, ensure_ascii=False, indent=1) + "\n" +
               "\n".join(lines))


HANDLERS = {"fare_search": tool_fare_search, "train_search": tool_train_search,
            "watch_add": tool_watch_add, "watch_del": tool_watch_del,
            "snapshot_get": tool_snapshot_get,
            "reverse_search": tool_reverse_search,
            "verify_release": tool_verify_release,
            "patrol_run": tool_patrol_run}


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
