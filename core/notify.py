# -*- coding: utf-8 -*-
"""Push channels: Bark (iOS), ServerChan (WeChat), plus console log."""
import datetime as dt
import json
import os

import requests

_ALERTS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "alerts.json")


def has_channel(cfg):
    """True when at least one real push channel (Bark/ServerChan) is set.
    Used to avoid consuming the 7d weekly-push timer with a console-only push."""
    p = cfg.get("push", {}) or {}
    return bool((p.get("bark_key") or "").strip()
                or (p.get("serverchan_sendkey") or "").strip())


def push_all(cfg, log, title, body, url="", route_id=None):
    p = cfg.get("push", {})
    results = []

    bark = (p.get("bark_key") or "").strip()
    if bark:
        try:
            payload = {
                "title": title,
                "body": body,
                "group": p.get("group", "机票低价提醒"),
                "isArchive": 1,
            }
            if url:
                payload["url"] = url
            if p.get("sound"):
                payload["sound"] = p["sound"]
            r = requests.post("https://api.day.app/" + bark, json=payload, timeout=15)
            if r.status_code == 200:
                results.append("bark:200")
            else:  # invalid/expired key must count as failure downstream
                results.append("bark:ERR HTTP " + str(r.status_code))
        except Exception as e:
            results.append("bark:ERR " + str(e))

    sc = (p.get("serverchan_sendkey") or "").strip()
    if sc:
        try:
            r = requests.post("https://sctapi.ftqq.com/" + sc + ".send",
                              data={"title": title, "desp": body}, timeout=15)
            ok = r.status_code == 200
            body_code = None
            if ok:  # ServerChan may answer 200 with an error body
                try:
                    body_code = int(r.json().get("code", 0))
                    ok = body_code == 0
                except Exception:
                    ok = False
            if ok:
                results.append("serverchan:200")
            elif r.status_code == 200:
                results.append("serverchan:ERR BODY code=" + str(body_code))
            else:
                results.append("serverchan:ERR HTTP " + str(r.status_code))
        except Exception as e:
            results.append("serverchan:ERR " + str(e))

    if not results:
        results.append("console-only(未配置推送key,详见report)")
    log.info("push -> " + ", ".join(results))
    _record_alert(title, body, url, route_id)
    return results


def _record_alert(title, body, url, route_id):
    try:
        os.makedirs(os.path.dirname(_ALERTS_FILE), exist_ok=True)
        history = []
        if os.path.exists(_ALERTS_FILE):
            with open(_ALERTS_FILE, encoding="utf-8") as f:
                history = json.load(f)
        now = dt.datetime.now().isoformat(timespec="seconds")
        last = history[-1] if history else None
        if (last and last.get("ts") == now and last.get("title") == title
                and last.get("body") == body):
            return  # duplicate burst (double-click / retry): keep one row
        history.append({
            "ts": now,
            "route": route_id or "",
            "title": title,
            "body": body,
            "url": url or "",
        })
        history = history[-200:]
        with open(_ALERTS_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
