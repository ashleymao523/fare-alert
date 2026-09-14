# -*- coding: utf-8 -*-
"""v0.41: restore a tools/backup.py archive into this checkout.

Usage: python -X utf8 tools/restore.py <fare-alert-backup-*.zip> [--yes]
Overwrites config.json + data state; refuses to run without --yes.
Restart the webui afterwards so in-memory state reloads.
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _safe_member(name):
    """Allow-list: only paths a backup.py archive may contain.
    Global rejections first (traversal / absolute / drive letters),
    then EXACT top-level names - a prefix like config.json/../../x
    cannot pass because only a literal 'config.json' member is
    allowed (v0.41 review P1)."""
    norm = name.replace("\\", "/")
    if not norm or norm.startswith("/"):
        return False
    head = norm.split("/", 1)[0]
    if ":" in head:  # windows drive letters / NTFS streams (C:/, C:\\)
        return False
    parts = [p for p in norm.split("/") if p and p != "."]
    if not parts or any(p == ".." for p in parts):
        return False
    if parts == ["config.json"]:
        return True
    return parts[0] == "data" and len(parts) > 1


def restore(zip_path, root=ROOT):
    """Returns (restored, skipped). Unsafe members are skipped, never
    written (zip-slip guard); a single failing member no longer aborts
    the whole restore (per-member fault isolation, v0.41 review P2)."""
    restored, skipped = [], []
    root_real = os.path.realpath(root)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            if not _safe_member(info.filename):
                skipped.append(info.filename)
                continue
            target = os.path.normpath(os.path.join(
                root, *info.filename.replace("\\", "/").split("/")))
            # defense in depth: lexical allow-list + realpath lock, so
            # even a future allow-list regression cannot escape root
            tr = os.path.realpath(target)
            if tr != root_real and not tr.startswith(root_real + os.sep):
                skipped.append(info.filename)
                continue
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(info) as src, open(target, "wb") as dst:
                    dst.write(src.read())
            except OSError:
                skipped.append(info.filename)  # e.g. dir/file clash
                continue
            restored.append(info.filename)
    return restored, skipped


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    yes = "--yes" in args
    positional = [a for a in args if not a.startswith("--")]
    if not positional:
        print("usage: python -X utf8 tools/restore.py <zip> [--yes]")
        return 2
    zp = positional[0]
    if not os.path.exists(zp):
        print("FAIL zip not found: " + zp)
        return 2
    if not yes:
        print("this OVERWRITES config.json + data state in " + ROOT)
        print("re-run with --yes to confirm")
        return 2
    restored, skipped = restore(zp)
    print("RESTORED %d files into %s" % (len(restored), ROOT))
    for r in restored[:20]:
        print("  + " + r)
    if len(restored) > 20:
        print("  ... and %d more" % (len(restored) - 20))
    if skipped:
        print("SKIPPED non-allowlisted entries:")
        for s in skipped[:10]:
            print("  - " + s)
    print("restart the webui now: powershell -NoProfile -ExecutionPolicy "
          "Bypass -File tools/restart_webui.ps1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
