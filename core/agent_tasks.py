# -*- coding: utf-8 -*-
"""v1.10: agent task ledger - every background job as a first-class agent.

The deploy has grown a set of specialized background jobs (full scan,
cabin patrol, dow balance, auto backup, fx refresh, health patrol,
weekly digest), each persisting its own status file with its own
timestamp flavor. This module reads them ALL and projects one uniform
ledger: per-agent {id, name, icon, last_run, next_due, status
(ok/late/idle), detail, manual_trigger}.

Observability-first: the existing worker loop stays the scheduler in
v1.10 - the ledger makes every "agent" visible/inspectable from the
UI task center, and the only execution surface added is a manual
trigger for the idempotent ones. Later versions can move scheduling
here task by task without touching the UI again."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

LATE_FACTOR = 1.5      # past 1.5x cadence => late, not merely due


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _iso(value):
    """epoch float or ISO string -> datetime, else None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value))
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(s[:19] if fmt.endswith("S")
                                     else s[:16], fmt)
        except ValueError:
            continue
    return None


def _fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M") if dt else None


def classify(last, cadence_minutes, now):
    """idle (never ran) / ok (within cadence) / late (past 1.5x)."""
    if last is None:
        return "idle"
    age = (now - last).total_seconds() / 60.0
    if age < 0:
        return "ok"                      # clock skew: don't cry wolf
    if age > cadence_minutes * LATE_FACTOR:
        return "late"
    return "ok"


def next_due(last, cadence_minutes, now):
    if last is None:
        return None
    return _fmt(last + timedelta(minutes=cadence_minutes))


def _agent(aid, name, icon, last, cadence_minutes, now, detail,
           manual=None, kind="scheduled"):
    return {
        "id": aid, "name": name, "icon": icon,
        "kind": kind,
        "cadence_minutes": cadence_minutes,
        "last_run": _fmt(last),
        "age_min": round((now - last).total_seconds() / 60.0, 1)
        if last else None,
        "next_due": next_due(last, cadence_minutes, now),
        "status": classify(last, cadence_minutes, now),
        "detail": detail,
        "manual_trigger": manual,
    }


def build_ledger(data_dir, cfg=None, now=None):
    """Project all background jobs into one agent ledger (pure reads)."""
    now = now or datetime.now()
    cfg = cfg or {}
    agents = []

    hb = _load(os.path.join(data_dir, "worker_heartbeat.json"))
    cad = int((cfg.get("schedule") or {}).get(
        "interval_minutes", 45) or 45)
    agents.append(_agent(
        "scan-all", "全量扫描", "🔍", _iso(hb.get("ts")), cad, now,
        "worker pid {p} · code v{v}".format(
            p=hb.get("pid"), v=hb.get("code_ver")),
        manual="/api/run"))

    state = _load(os.path.join(data_dir, "state.json"))
    cp = (state.get("_cabin_patrol") or {})
    cw = (cfg.get("cabin_watch") or {})
    # v1.15.1: during throttle backoff the effective cadence IS the
    # stretched interval - the card counts down to the real next fire
    # instead of flagging the agent late mid-backoff.
    cp_eff = int(cp.get("interval_effective_minutes") or 0)
    agents.append(_agent(
        "cabin-patrol", "公务舱巡检", "👔", _iso(cp.get("last_run")),
        cp_eff or int(cw.get("refresh_minutes", 30) or 30), now,
        str(cp.get("last_status") or "尚未巡检"),
        manual="/api/tasks/cabin-patrol/run"))

    db = _load(os.path.join(data_dir, "dow_balance.json"))
    agents.append(_agent(
        "dow-balance", "班期平衡", "📅", _iso(db.get("last_run")),
        12 * 60, now,
        "done 键 {n} 个 (4-12h 自适应节流)".format(
            n=len(db.get("done") or {}))))

    ab = _load(os.path.join(data_dir, "auto_backup.json"))
    agents.append(_agent(
        "auto-backup", "每日备份", "📦", _iso(ab.get("ts")),
        24 * 60, now,
        "{d} · {n} 项".format(d=ab.get("date"), n=ab.get("items"))))

    fx = _load(os.path.join(data_dir, "fx_cache.json"))
    agents.append(_agent(
        "fx-refresh", "汇率刷新", "💱", _iso(fx.get("ts")),
        24 * 60, now,
        "EUR→CNY {r} ({s} {d}){st}".format(
            r=fx.get("rate"), s=fx.get("source"), d=fx.get("date"),
            st=" · 陈旧" if fx.get("stale") else "")))

    hp = _load(os.path.join(data_dir, "patrol_last.json"))
    agents.append(_agent(
        "health-patrol", "健康巡检", "🩺", _iso(hp.get("ts")),
        24 * 60, now,
        "verdict {v} · {n} 项检查".format(
            v=hp.get("verdict"), n=len(hp.get("checks") or {}))))

    wk = _load(os.path.join(data_dir, "weekly_push.json"))
    agents.append(_agent(
        "weekly-digest", "洞察周报", "📈", _iso(wk.get("ts")),
        7 * 24 * 60, now,
        str(wk.get("week") or "首次周报待生成"), kind="weekly"))

    return {"agents": agents,
            "updated_at": now.strftime("%Y-%m-%dT%H:%M")}
