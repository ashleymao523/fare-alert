# -*- coding: utf-8 -*-
"""v0.99: daily ECB EUR->CNY reference rate.

The booking.com precise-query fill (the channel that answers grey
calendar dates with real per-date quotes) converted EUR totals with a
hardcoded 7.8 - the single largest error term on those reference
rows. ECB publishes a daily reference rate every business day; both
endpoints below need NO key (unlike Amadeus):

  1. frankfurter.app        - fast keyless ECB mirror (primary)
  2. data-api.ecb.europa.eu - official ECB SDW CSV (fallback)

Resolution chain: live rate -> yesterday's cache (flagged stale, any
age) -> cfg booking_fill.fx_eur_cny (default 7.8). Every hop is
observable via fx_snapshot(), surfaced in /api/health, so a wrong
rate can never hide behind the fixed fallback.
"""
from __future__ import annotations

import json
import os
import time

import requests


FRANKFURTER_URL = "https://api.frankfurter.app/latest"
ECB_CSV_URL = ("https://data-api.ecb.europa.eu/service/data/EXR/"
               "D.CNY.EUR.SP00.A")
FALLBACK_FX = 7.8
FX_TTL_S = 12 * 3600          # ECB publishes once/day; refresh 2x/day


def cache_path(data_dir):
    return os.path.join(data_dir, "fx_cache.json")


def _read_cache(path):
    try:
        with open(path, encoding="utf-8") as f:
            j = json.load(f)
        return j if isinstance(j, dict) else {}
    except Exception:
        return {}


def _atomic_write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _fetch_frankfurter(session, net_cfg):
    r = session.get(FRANKFURTER_URL, params={"from": "EUR", "to": "CNY"},
                    timeout=net_cfg.get("timeout_seconds", 25))
    r.raise_for_status()
    j = r.json()
    rate = float(((j.get("rates") or {}).get("CNY")) or 0)
    if rate <= 0:
        raise ValueError("frankfurter bad payload: " + str(j)[:120])
    return rate, str(j.get("date") or "")


def _fetch_ecb(session, net_cfg):
    r = session.get(ECB_CSV_URL,
                    params={"lastNObservations": 1,
                            "format": "csvdata"},
                    timeout=net_cfg.get("timeout_seconds", 25))
    r.raise_for_status()
    rate, date = 0.0, ""
    lines = [ln for ln in (r.text or "").splitlines() if ln.strip()]
    if lines:
        cols = lines[0].split(",")
        try:
            vi, di = cols.index("OBS_VALUE"), cols.index("TIME_PERIOD")
            last = lines[-1].split(",")
            rate, date = float(last[vi]), last[di]
        except (ValueError, IndexError):
            pass
    if rate <= 0:
        raise ValueError("ecb csv bad payload: " + (r.text or "")[:120])
    return rate, date


def get_rate(session=None, cfg=None, data_dir="data", now=None,
             force=False):
    """Return {rate, date, source, ts, stale}; never raises."""
    cfg = cfg if isinstance(cfg, dict) else {}
    bk_cfg = cfg.get("booking_fill") or {}
    path = cache_path(data_dir)
    now = float(now if now is not None else time.time())
    fixed = float(bk_cfg.get("fx_eur_cny", FALLBACK_FX) or FALLBACK_FX)
    # default "fixed": the legacy 7.8 keeps unit tests and offline
    # deployments zero-network; set booking_fill.fx_mode="ecb" to
    # enable the daily-rate chain (documented in config.example.json).
    if str(bk_cfg.get("fx_mode") or "fixed").strip().lower() != "ecb":
        return {"rate": fixed, "date": "", "source": "fixed",
                "ts": now, "stale": False}
    cached = _read_cache(path)
    fresh = (cached and float(cached.get("rate") or 0) > 0
             and (now - float(cached.get("ts") or 0)) <= FX_TTL_S)
    if fresh and not force:
        out = dict(cached)
        out["stale"] = False
        return out
    session = session or requests.Session()
    net_cfg = cfg.get("network") or {}
    for name, fn in (("frankfurter", _fetch_frankfurter),
                     ("ecb-official", _fetch_ecb)):
        try:
            rate, date = fn(session, net_cfg)
        except Exception:
            continue
        out = {"rate": round(rate, 4), "date": date, "source": name,
               "ts": now, "stale": False}
        try:
            _atomic_write(path, out)
        except Exception:
            pass
        return out
    if cached and float(cached.get("rate") or 0) > 0:
        out = dict(cached)
        out["stale"] = True
        return out
    return {"rate": fixed, "date": "", "source": "fallback",
            "ts": now, "stale": True}


def fx_snapshot(data_dir="data"):
    """Health observability hook: last resolved rate block."""
    return _read_cache(cache_path(data_dir)) or None
