# -*- coding: utf-8 -*-
"""v0.41/v0.86: one-command state backup for device migration
(Win/Mac/Linux).

Zips config.json + the durable data/ state into backups/ so the whole
component (routes, thresholds, sched board db, alert state, caches) can
move to another machine. Cross-device restore: tools/restore.py.
v0.86: the zip carries bundle_manifest.json (per-member sha256 +
code_ver) so restore.py can refuse a corrupted or hand-tampered
archive, and ITEMS regained the durable state added after v0.41
(price history, cabin ring, point-fill cache, board-teaching queue).

Usage: python -X utf8 tools/backup.py
"""
import datetime as dt
import hashlib
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MANIFEST_NAME = "bundle_manifest.json"

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
    # v0.86: durable state introduced after v0.41 - without these a
    # migration silently loses the weekly/drop history, the business
    # cabin ring, the manual point-fill backfill cache and the v0.83
    # board-teaching deposit queue (Sunday backfill would regress).
    "data/history.json",
    "data/cabin_history.json",
    "data/point_fill_cache.json",
    "data/sched_deposit.json",
    "data/report",  # weekly report history (directory, recursive)
]


def _code_ver(root):
    """CODE_VERSION of the checkout being zipped, "" when the root is
    a bare test fixture with no core/ package."""
    try:
        from core.version import CODE_VERSION  # noqa: E402
        return CODE_VERSION
    except Exception:
        return ""


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
    # v0.86: seal the archive with a sha256 manifest of what is
    # actually inside the zip (not what the sources said) so restore
    # detects any later corruption or hand-editing of members.
    digests = {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir() or info.filename == MANIFEST_NAME:
                continue
            h = hashlib.sha256(z.read(info.filename)).hexdigest()
            digests[info.filename.replace(os.sep, "/")] = h
    manifest = {
        "format": 2,
        "code_ver": _code_ver(root),
        "exported_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sha256": digests,
        "included": included,
        "skipped": skipped,
    }
    with zipfile.ZipFile(path, "a") as z:
        z.writestr(MANIFEST_NAME,
                   json.dumps(manifest, ensure_ascii=False, indent=1))
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
