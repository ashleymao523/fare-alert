#!/usr/bin/env python3
"""Probe the qunar price calendar gateway with various param combos."""
import datetime
import json
import sys
import time

import requests

URL = "https://gw.flight.qunar.com/api/f/priceCalendar"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                   "Mobile/15E148 Safari/604.1"),
    "Referer": "https://m.flight.qunar.com/",
    "Accept": "application/json",
}


def probe(dep, arr, params, tag):
    try:
        r = requests.get(URL, params=params, headers=HEADERS, timeout=20)
        j = r.json()
    except Exception as e:
        print(tag, "HTTP/JSON error:", str(e)[:120])
        return
    code = (j.get("bstatus") or {}).get("code")
    data = j.get("data") or {}
    flights = data.get("gflights") or []
    dates = sorted({e.get("date") for e in flights if e.get("date")})
    today = datetime.date.today()
    horizon = ""
    if dates:
        last = datetime.date.fromisoformat(dates[-1])
        horizon = "horizon={}d".format((last - today).days)
    sample = ""
    if flights:
        e = flights[0]
        sample = " sample_keys=" + ",".join(sorted(e.keys()))
    print("{} code={} rows={} uniq_dates={} {}{}".format(
        tag, code, len(flights), len(dates), horizon, sample))
    if len(sys.argv) > 2 and sys.argv[2] == "dump":
        open("data/probe_{}.json".format(tag.replace("/", "_")),
             "w", encoding="utf-8").write(json.dumps(j, ensure_ascii=False, indent=1))


def main():
    dep = sys.argv[1] if len(sys.argv) > 1 else "杭州"
    arr = "重庆"
    combos = [
        ("base", {"dep": dep, "arr": arr, "days": "", "priceType": "1"}),
        ("days90", {"dep": dep, "arr": arr, "days": "90", "priceType": "1"}),
        ("days60", {"dep": dep, "arr": arr, "days": "60", "priceType": "1"}),
        ("ptype0", {"dep": dep, "arr": arr, "days": "", "priceType": "0"}),
        ("ptype2", {"dep": dep, "arr": arr, "days": "", "priceType": "2"}),
        ("nodays", {"dep": dep, "arr": arr, "priceType": "1"}),
        ("fromdate", {"dep": dep, "arr": arr, "fromDate":
                      datetime.date.today().isoformat(), "days": "", "priceType": "1"}),
    ]
    for tag, params in combos:
        probe(dep, arr, params, tag)
        time.sleep(1.2)


if __name__ == "__main__":
    main()
