# -*- coding: utf-8 -*-
"""Cross-device migration packer (v1.32).

Builds fare-alert-migration-vX.Y.zip in the PARENT directory containing:
  - all git-tracked files (code, built frontend, docs, tests)
  - the full .git history (keeps push ability on the new device)
  - config.json + durable data states (see DATA_ITEMS) + data/report/
  - the CDP seed profile data/edge_prof_recon_warm (cdp_cabin rebuilds
    itself from this seed on first cabin capture - see 迁移指南.md)

Excluded on purpose: the 1.1GB live cdp_cabin profile, ~35 debug
profiles, backups/, __pycache__, probe leftovers.
"""
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.dirname(ROOT)
VERSION = "v1.32"
FOLDER = "fare-alert"
OUT_PATH = os.path.join(OUT_DIR, "fare-alert-migration-%s.zip" % VERSION)

DATA_ITEMS = [
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
    "data/history.json",
    "data/cabin_history.json",
    "data/point_fill_cache.json",
    "data/sched_deposit.json",
    "data/cdp_cabin_ledger.json",
]
DATA_DIRS = ["data/report", os.path.join("data", "edge_prof_recon_warm"), "session"]
SKIP_NAMES = {"__pycache__"}
SKIP_SUFFIXES = (".pyc", ".pyo")


def _git_files():
    # quotePath=false keeps CJK filenames as raw UTF-8 instead of octal
    # escapes - with the default a name like 部署指南.md arrives as
    # "docs\351\203\250..." and the file silently drops out of the zip.
    proc = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-files"],
        cwd=ROOT, capture_output=True,
    )
    out = proc.stdout.decode("utf-8", "replace")
    files = []
    for line in out.splitlines():
        rel = line.strip().replace("/", os.sep)
        if rel:
            files.append(rel)
    return files


def _walk(rel_dir):
    found = []
    base = os.path.join(ROOT, rel_dir)
    for cur, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_NAMES]
        for name in names:
            if name.endswith(SKIP_SUFFIXES):
                continue
            abs_p = os.path.join(cur, name)
            found.append(os.path.relpath(abs_p, ROOT))
    return found


def collect():
    rels = set(_git_files())
    rels.update(DATA_DIRS)
    rels.update(DATA_ITEMS)
    rels.add(os.path.join("tools", "pack_migration.py"))
    rels.add("迁移指南.md")

    singles, dirs = [], []
    for rel in sorted(rels):
        if rel in DATA_DIRS:
            dirs.append(rel)
        elif os.path.isfile(os.path.join(ROOT, rel)):
            singles.append(rel)
        elif rel not in DATA_ITEMS:
            print("WARN git-tracked path missing on disk: %s" % rel)

    entries = list(singles)
    for d in dirs:
        entries.extend(_walk(d))
    entries.extend(_walk(".git"))
    return sorted(set(entries))


def main():
    entries = collect()
    total = 0
    skipped = []
    print("packing %d files -> %s" % (len(entries), OUT_PATH))
    with zipfile.ZipFile(OUT_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, rel in enumerate(entries):
            if (i % 2000) == 0:
                print("  ...%d/%d (%.1f MB read)" % (i, len(entries), total / 1048576))
            abs_p = os.path.join(ROOT, rel)
            arc = FOLDER + "/" + rel.replace(os.sep, "/")
            try:
                zf.write(abs_p, arc)
                total += os.path.getsize(abs_p)
            except OSError as exc:
                skipped.append((rel, str(exc)))
    size = os.path.getsize(OUT_PATH)
    print("DONE zip=%.1f MB raw=%.1f MB files=%d skipped=%d"
          % (size / 1048576, total / 1048576, len(entries) - len(skipped), len(skipped)))
    for rel, why in skipped[:20]:
        print("  SKIP %s: %s" % (rel, why))


if __name__ == "__main__":
    sys.exit(main())
