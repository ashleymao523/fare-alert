# -*- coding: utf-8 -*-
"""CLI wrapper: re-run flight-time enrichment over an existing snapshot.

The logic lives in core/reenrich.py (v0.41) so the daily patrol can call
 it too; this script stays for manual/offline use:
    python -X utf8 tools/reenrich_times.py [--dry]
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.reenrich import reenrich_snapshot  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    out = reenrich_snapshot(ROOT, dry=args.dry)
    for r in out["per_route"]:
        print("%-16s deals=%-3d dep %d/%d"
              % (r["id"], r["deals"], r["dep_covered"], r["dep_total"]))
    print("TOTAL dep %d/%d across %d routes"
          % (out["dep_covered"], out["dep_total"], out["routes"]))
    if args.dry:
        print("(dry run, snapshot untouched)")
    elif out["routes"]:
        print("snapshot rewritten (backup saved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
