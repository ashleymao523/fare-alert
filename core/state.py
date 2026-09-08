# -*- coding: utf-8 -*-
"""Persistent state for dedupe/cooldown of alerts."""
import datetime as dt
import json
import os


def load_state(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"routes": {}}


def save_state(path, state):
    # prune dates already in the past
    today = dt.date.today().isoformat()
    for rid in state.get("routes", {}):
        dates = state["routes"][rid].get("dates", {})
        for d in [k for k in dates if k < today]:
            dates.pop(d, None)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
