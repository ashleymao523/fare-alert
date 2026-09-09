#!/usr/bin/env python3
"""Report missing-price dates per route from data/snapshot.json."""
import datetime
import json
import sys


def main() -> int:
    snap = json.load(open("data/snapshot.json", encoding="utf-8"))
    for r in snap.get("routes", []):
        d0, d1 = r.get("window", ["", ""])
        days, d = [], datetime.date.fromisoformat(d0)
        while d.isoformat() <= d1:
            days.append(d.isoformat())
            d += datetime.timedelta(days=1)
        have = {x.get("date") for x in r.get("deals", [])}
        missing = [x for x in days if x not in have]
        print("{} intl={} days={} have={} missing={}".format(
            r.get("id"), r.get("intl"), len(days), len(have), len(missing)))
        if missing:
            print("  first16:", ",".join(missing[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
