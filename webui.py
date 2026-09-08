# -*- coding: utf-8 -*-
"""FareAlert Web UI: local dashboard, config editor, manual run & push test."""
import json
import os
import re
import threading

from flask import Flask, jsonify, render_template, request, send_from_directory

import main as runner
from core.config import load_config, save_config
from core.notify import push_all
from core.sources import SOURCE_REGISTRY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "snapshot.json")
ALERTS_PATH = os.path.join(DATA_DIR, "alerts.json")
LOG_PATH = os.path.join(DATA_DIR, "run.log")
REPORT_DIR = os.path.join(DATA_DIR, "report")

MASK = "***"
SECRET_KEYS = ("bark_key", "serverchan_sendkey")
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

app = Flask(__name__,
            template_folder=os.path.join("webui", "templates"),
            static_folder=os.path.join("webui", "static"))
_lock = threading.RLock()
_log = runner.setup_logging()


def _deep_copy(x):
    return json.loads(json.dumps(x))


def _mask(cfg):
    out = _deep_copy(cfg)
    push = out.setdefault("push", {})
    for k in SECRET_KEYS:
        push[k] = MASK if (push.get(k) or "").strip() else ""
    return out


def _secrets_set(cfg):
    push = cfg.get("push", {})
    return {k: bool((push.get(k) or "").strip()) for k in SECRET_KEYS}


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _tail(path, n=300):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except Exception:
        return ""


def _validate_config(body, current):
    if not isinstance(body, dict):
        raise ValueError("config must be an object")
    cfg = _deep_copy(body)

    routes = cfg.get("routes")
    if not isinstance(routes, list) or not routes:
        raise ValueError("routes must be a non-empty list")
    ids = set()
    for r in routes:
        if not isinstance(r, dict):
            raise ValueError("route must be an object")
        rid = str(r.get("id", ""))
        if not _ID_RE.match(rid):
            raise ValueError("线路id只能包含字母/数字/-/_: " + rid)
        if rid in ids:
            raise ValueError("线路id重复: " + rid)
        ids.add(rid)
        for k in ("from_city", "to_city"):
            v = str(r.get(k, "")).strip()
            if not v:
                raise ValueError("出发/到达城市不能为空")
            r[k] = v
        wd = r.get("window_days", 60)
        if not isinstance(wd, int) or not (1 <= wd <= 365):
            raise ValueError("查询窗口必须是1-365的整数")
        th = r.get("threshold_total", 500)
        if not isinstance(th, (int, float)) or th <= 0:
            raise ValueError("心理价位必须是正数")
        tc = r.get("train_compare") or {}
        if not isinstance(tc, dict):
            raise ValueError("train_compare必须是对象")
        pairs = tc.get("station_pairs", [])
        if not isinstance(pairs, list):
            raise ValueError("station_pairs必须是列表")
        clean_pairs = []
        for p in pairs:
            if not (isinstance(p, list) and len(p) == 2
                    and all(isinstance(x, str) and x.strip() for x in p)):
                raise ValueError("每个车站对必须是两个非空站名")
            clean_pairs.append([p[0].strip(), p[1].strip()])
        tc["station_pairs"] = clean_pairs
        tc["enabled"] = bool(tc.get("enabled", True))
        r["train_compare"] = tc
        r["window_days"] = wd
        r["threshold_total"] = float(th)
    cfg["routes"] = routes

    tax = cfg.get("tax") or {}
    if not isinstance(tax, dict):
        raise ValueError("tax必须是对象")
    for k in ("airport_fee", "fuel_surcharge"):
        v = tax.get(k, 0)
        if not isinstance(v, (int, float)) or v < 0:
            raise ValueError(k + "必须是非负数字")
        tax[k] = float(v)
    tax["calendar_price_includes_tax"] = bool(tax.get("calendar_price_includes_tax", False))
    cfg["tax"] = tax

    sch = cfg.get("schedule") or {}
    if not isinstance(sch, dict):
        raise ValueError("schedule必须是对象")
    iv = sch.get("interval_minutes", 45)
    if not isinstance(iv, int) or iv < 5:
        raise ValueError("查询间隔至少5分钟")
    sch["interval_minutes"] = iv
    sch["jitter_minutes"] = max(0, int(sch.get("jitter_minutes", 10)))
    cfg["schedule"] = sch

    src = (cfg.get("sources") or {}).get("enabled")
    if src is not None and not isinstance(src, dict):
        raise ValueError("sources.enabled必须是对象")
    cur_src = (current.get("sources") or {}).get("enabled") or {}
    clean_src = {}
    for k in SOURCE_REGISTRY:
        if src is not None and k in src:
            clean_src[k] = bool(src[k])
        else:
            clean_src[k] = bool(cur_src.get(k, False))
    cfg["sources"] = {"enabled": clean_src}

    push = cfg.get("push") or {}
    if not isinstance(push, dict):
        raise ValueError("push必须是对象")
    cur_push = current.get("push") or {}
    for k in SECRET_KEYS:
        v = str(push.get(k) or "")
        push[k] = (cur_push.get(k) or "") if v == MASK else v.strip()
    for k in ("group", "sound"):
        push[k] = str(push.get(k) or "")
    cfg["push"] = push

    al = cfg.get("alert") or {}
    if not isinstance(al, dict):
        raise ValueError("alert必须是对象")
    al["top_n"] = min(10, max(1, int(al.get("top_n", 5))))
    al["realert_drop"] = max(0.0, float(al.get("realert_drop", 5)))
    al["cooldown_hours"] = max(0.0, float(al.get("cooldown_hours", 6)))
    cfg["alert"] = al

    w = cfg.get("webui") or {}
    if not isinstance(w, dict):
        raise ValueError("webui必须是对象")
    host = str(w.get("host") or "127.0.0.1").strip()
    port = int(w.get("port") or 8765)
    if not (1 <= port <= 65535):
        raise ValueError("端口号无效")
    cfg["webui"] = {"host": host, "port": port}

    for k in ("baggage_policy", "network"):
        v = cfg.get(k)
        if not isinstance(v, dict) or not v:
            cfg[k] = current.get(k, {})
    return cfg


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/snapshot")
def api_snapshot():
    return jsonify({"snapshot": _read_json(SNAPSHOT_PATH, None)})


@app.get("/api/config")
def api_get_config():
    cfg = load_config(CONFIG_PATH)
    return jsonify({
        "config": _mask(cfg),
        "secrets_set": _secrets_set(cfg),
        "sources": SOURCE_REGISTRY,
    })


@app.post("/api/config")
def api_post_config():
    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"ok": False, "error": "无效的JSON"}), 400
    with _lock:
        current = load_config(CONFIG_PATH)
        try:
            cfg = _validate_config(body, current)
            save_config(CONFIG_PATH, cfg)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({
        "ok": True,
        "config": _mask(cfg),
        "secrets_set": _secrets_set(cfg),
        "sources": SOURCE_REGISTRY,
    })


@app.post("/api/run")
def api_run():
    body = request.get_json(silent=True) or {}
    push = bool(body.get("push", True))
    with _lock:
        cfg = load_config(CONFIG_PATH)
        try:
            snapshot = runner.run_once(cfg, _log, push_enabled=push)
        except Exception as e:
            _log.error("manual run failed: %s", e)
            return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True, "snapshot": snapshot})


@app.post("/api/test-push")
def api_test_push():
    cfg = load_config(CONFIG_PATH)
    results = push_all(cfg, _log, "✈️ FareAlert 测试推送",
                       "推送通道配置成功!这是一条测试消息。", url="")
    return jsonify({"ok": True, "results": results})


@app.get("/api/alerts")
def api_alerts():
    history = _read_json(ALERTS_PATH, [])
    if isinstance(history, list):
        history = list(reversed(history[-50:]))
    else:
        history = []
    return jsonify({"alerts": history})


@app.get("/api/log")
def api_log():
    return jsonify({"log": _tail(LOG_PATH, 300)})


@app.get("/report/<path:subpath>")
def api_report(subpath):
    return send_from_directory(REPORT_DIR, subpath)


def main():
    cfg = load_config(CONFIG_PATH)
    w = cfg.get("webui", {})
    host = w.get("host", "127.0.0.1")
    port = int(w.get("port", 8765))
    shown = "127.0.0.1" if host == "0.0.0.0" else host
    print("FareAlert Web UI: http://" + shown + ":" + str(port))
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()

