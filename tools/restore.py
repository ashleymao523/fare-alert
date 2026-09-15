# -*- coding: utf-8 -*-
"""v0.41/v0.86: restore a tools/backup.py archive into this checkout.

Usage: python -X utf8 tools/restore.py <fare-alert-backup-*.zip> [--yes]
Overwrites config.json + data state; refuses to run without --yes.
Restart the webui afterwards so in-memory state reloads.
v0.86: when the archive carries bundle_manifest.json every member's
sha256 is verified first - a corrupted or hand-edited zip is refused
outright (--force overrides, at your own risk). main() also drops a
safety backup of the CURRENT state into backups/ before overwriting,
so a bad import is itself one-command recoverable.
"""
import datetime as dt
import hashlib
import json
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backup  # noqa: E402  (same dir; safety backups on import)

MANIFEST_NAME = backup.MANIFEST_NAME


class ManifestError(Exception):
    """v0.86: archive content does not match its sha256 manifest."""


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
    if parts == [MANIFEST_NAME]:  # v0.86 seal written by backup.py
        return True
    return parts[0] == "data" and len(parts) > 1


def read_manifest(zip_path):
    """Returns the parsed bundle_manifest.json, or None for a
    v0.41-format archive that predates sealing."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            if MANIFEST_NAME not in z.namelist():
                return None
            return json.loads(z.read(MANIFEST_NAME).decode("utf-8"))
    except (OSError, ValueError, KeyError):
        return None


def verify_manifest(zip_path):
    """Raises ManifestError listing every member whose bytes do not
    match the manifest digest (or that the manifest promised but the
    archive lacks). Quiet pass for unsealed v0.41 archives."""
    mf = read_manifest(zip_path)
    if not mf:
        return None
    want = mf.get("sha256") or {}
    bad = []
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        for member, digest in want.items():
            if member not in names:
                bad.append(member + " (missing)")
                continue
            got = hashlib.sha256(z.read(member)).hexdigest()
            if got != digest:
                bad.append(member)
    if bad:
        raise ManifestError(
            "sha256 mismatch: " + ", ".join(bad[:5]) +
            (" (+%d more)" % (len(bad) - 5) if len(bad) > 5 else ""))
    return mf


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
            if info.filename == MANIFEST_NAME:
                continue  # v0.86: seal metadata, not state to restore
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


def safety_backup(root=ROOT):
    """v0.86: zip the current state before an import overwrites it.
    Returns the safety zip path, or None when writing failed (the
    caller decides whether to proceed anyway)."""
    try:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(root, "backups")
        zpath, _inc, _sk = backup.make_backup(root=root, dest_dir=dest)
        pre = os.path.join(dest, "pre-restore-safety-%s.zip" % stamp)
        os.replace(zpath, pre)
        return pre
    except OSError:
        return None


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
    force = "--force" in args
    try:
        verify_manifest(zp)
    except ManifestError as e:
        if not force:
            print("FAIL archive failed integrity check: " + str(e))
            print("re-export on the source device, or re-run with "
                  "--force to override (unsafe)")
            return 2
        print("WARN integrity check failed, --force given: " + str(e))
    mf = read_manifest(zp)
    if mf and mf.get("code_ver"):
        print("bundle exported by code_ver " + mf["code_ver"] +
              " at " + str(mf.get("exported_at", "?")))
    if not yes:
        print("this OVERWRITES config.json + data state in " + ROOT)
        print("re-run with --yes to confirm")
        return 2
    safety = safety_backup()
    if safety:
        print("SAFETY " + safety)
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
