# -*- coding: utf-8 -*-
"""v0.41: one-command state backup for device migration (Win/Mac/Linux).

Zips config.json + the durable data/ state into backups/ so the whole
component (routes, thresholds, sched board db, alert state, caches) can
move to another machine. Cross-device restore: tools/restore.py.

Usage: python -X utf8 tools/backup.py
"""
import datetime as dt
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# durable state worth carrying to a new device (missing files skipped)
ITEMS = [
    "config.json",
    "data/snapshot.json",
    "data/flight_sched_db.json",
    "data/state.json",
    "data/travel_cache.json",
    "data/train_cache.json",
    "data/reverse_cache.json",
    "data/stations.json",
    "data/city_photos.json",
    "data/patrol_last.json",
    "data/health.json",
    "data/worker_heartbeat.json",
    "data/board_fetch_log.json",
    "data/report",  # weekly report history (directory, recursive)
]


def make_backup(root=ROOT, dest_dir=None):
    """Returns (zip_path, included, skipped). Only touches backups/."""
    dest_dir = dest_dir or os.path.join(root, "backups")
    os.makedirs(dest_dir, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(dest_dir, "fare-alert-backup-%s.zip" % stamp)
    included, skipped = [], []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in ITEMS:
            src = os.path.join(root, rel.replace("/", os.sep))
            if not os.path.exists(src):
                skipped.append(rel)
                continue
            if os.path.isdir(src):
                for base, _dirs, files in os.walk(src):
                    for fn in files:
                        fp = os.path.join(base, fn)
                        z.write(fp, os.path.relpath(fp, root))
                included.append(rel + "/")
            else:
                z.write(src, rel)
                included.append(rel)
    return path, included, skipped


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path, included, skipped = make_backup()
    print("BACKUP " + path)
    print("included %d items:" % len(included))
    for i in included:
        print("  + " + i)
    if skipped:
        print("skipped (not present, harmless):")
        for s in skipped:
            print("  - " + s)
    print("restore on the target device with: "
          "python -X utf8 tools/restore.py <zip>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
