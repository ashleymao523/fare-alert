# -*- coding: utf-8 -*-
"""v0.75: scheduled daily backup of the durable state.

Reuses the audited tools/backup.py zip core; adds the three pieces a
self-running deployment needs: a once-per-day guard (marker file in
data/), retention (keep the newest N archives) and an error status the
health endpoint can surface."""
import datetime as _dt
import glob
import json
import os
import time


def maybe_daily_backup(root, data_dir, keep=7, now=None):
    """One fare-alert-backup-*.zip per calendar day into <root>/backups.
    Returns {"status": created|skip|error, ...} - never raises, a
    broken backup must not take the worker loop down."""
    now = now or time.time()
    today = _dt.date.fromtimestamp(now).isoformat()
    marker = os.path.join(data_dir, "auto_backup.json")
    try:
        with open(marker, encoding="utf-8") as f:
            if json.load(f).get("date") == today:
                return {"status": "skip", "date": today}
    except Exception:
        pass
    try:
        from tools.backup import make_backup
        path, included, _skipped = make_backup(root=root)
    except Exception as e:
        return {"status": "error", "date": today, "error": str(e)[:120]}
    bdir = os.path.join(root, "backups")
    removed = []
    for old in sorted(glob.glob(os.path.join(
            bdir, "fare-alert-backup-*.zip")))[:-keep] if keep else []:
        try:
            os.remove(old)
            removed.append(os.path.basename(old))
        except Exception:
            pass
    rec = {"date": today, "path": os.path.basename(path),
           "ts": time.time(), "items": len(included),
           "removed": removed}
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(marker, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
    except Exception:
        pass
    rec["status"] = "created"
    return rec
