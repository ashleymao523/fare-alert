# -*- coding: utf-8 -*-
"""v0.40: one-shot system patrol core (extracted from mcp_server).

Aggregates /api/health + push readiness into a verdict and archives it to
data/patrol_last.json. Both callers share this single implementation:
  - mcp_server.tool_patrol_run  (agent / manual inspector)
  - core.revive.patrol_once     (daily 09:00 schedule inside webui)

Seams (config_loader / health_fetch / push) keep it unit-testable with
zero real HTTP and zero real pushes. The default health_fetch only ever
talks to 127.0.0.1, so a dropped seam still cannot cause an external
request (AGENTS.md red line #1).
"""
import datetime as dt
import json
import os
import urllib.request


class _SilentLog:
    """push_all only needs .info/.warning to exist."""

    def info(self, *a):
        pass

    def warning(self, *a):
        pass


def _fetch_health(port):
    with urllib.request.urlopen(
            "http://127.0.0.1:%d/api/health" % port, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _default_push(cfg, title, body, url=""):
    from core.notify import has_channel, push_all
    if not has_channel(cfg):
        return False
    push_all(cfg, _SilentLog(), title, body, url=url)
    return True


def run_patrol(base_dir, notify=False, config_loader=None,
               health_fetch=None, push=None):
    """Run one patrol pass; returns the archived doc (never pushes unless
    notify=True AND the verdict is unhealthy AND a channel is ready)."""
    if config_loader is None:
        from core.config import load_config as config_loader
    if health_fetch is None:
        health_fetch = _fetch_health
    if push is None:
        push = _default_push

    port = 8765
    try:
        cfg = config_loader(os.path.join(base_dir, "config.json"))
        port = int((cfg.get("webui") or {}).get("port") or 8765)
    except Exception:
        cfg = {}
    body = health_fetch(port)

    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "status": "ok" if ok else "warn",
                       "detail": detail})

    snap_age = (body.get("snapshot") or {}).get("age_min")
    add("snapshot-fresh", snap_age is not None and snap_age < 1500,
        "age_min=%s" % snap_age)
    wk = body.get("worker") or {}
    wstate = ("alive" if (wk.get("ok") and wk.get("age_min", 999) < 120)
              else ("stale" if wk else "none"))
    add("worker-heartbeat", wstate == "alive", "state=%s" % wstate)
    rv = body.get("revive") or {}
    sup = (rv.get("supervisor") or {}).get("enabled")
    add("daily-revive", bool(sup), "supervisor=%s" % sup)
    covered = ((body.get("board") or {}).get("weekdays_covered"))
    add("board-dow-coverage", covered == 7, "covered=%s/7" % covered)
    push_cfg = cfg.get("push") or {}
    ch = {"bark": bool((push_cfg.get("bark_key") or "").strip()),
          "serverchan": bool((push_cfg.get("serverchan_sendkey") or "").strip())}
    weekly_on = bool(push_cfg.get("weekly_enabled"))
    add("push-channel", any(ch.values()),
        "bark=%s serverchan=%s weekly_enabled=%s"
        % (ch["bark"], ch["serverchan"], weekly_on))

    verdict = "healthy" if all(c["status"] == "ok" for c in checks) else "warn"
    notified = False
    if notify and verdict != "healthy":
        bad = [c["name"] for c in checks if c["status"] != "ok"]
        notified = bool(push(cfg, "FareAlert 巡检异常",
                             "以下检查未通过: " + ", ".join(bad), url=""))
    doc = {"ts": dt.datetime.now().isoformat(timespec="seconds"),
           "verdict": verdict, "checks": checks, "notified": notified,
           "health": {"ok": body.get("ok"),
                      "snapshot_age_min": snap_age,
                      "worker": wstate,
                      "dows_covered": covered}}
    patrol_path = os.path.join(base_dir, "data", "patrol_last.json")
    try:
        os.makedirs(os.path.dirname(patrol_path), exist_ok=True)
        with open(patrol_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
    except Exception as e:
        doc["archive_error"] = repr(e)[:160]
    doc["notified"] = notified
    return doc
