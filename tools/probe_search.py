#!/usr/bin/env python3
"""Probe candidate per-date qunar flight-search endpoints."""
import json
import sys
import time

import requests

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

CANDIDATES = [
    ("search1", "https://m.flight.qunar.com/h5flight/api/domestic/search",
     {"dep": "杭州", "arr": "重庆", "date": "2026-09-20",
      "from": "priceCalendar", "child": "0", "baby": "0", "cabin": "0"}),
    ("search2", "https://m.flight.qunar.com/h5flight/api/domestic/search",
     {"depCity": "杭州", "arrCity": "重庆", "departureDate": "2026-09-20",
      "from": "priceCalendar"}),
    ("lowprice", "https://m.flight.qunar.com/h5flight/api/domestic/lowprice",
     {"dep": "杭州", "arr": "重庆", "date": "2026-09-20"}),
    ("price1", "https://m.flight.qunar.com/h5flight/api/domestic/price",
     {"dep": "杭州", "arr": "重庆", "date": "2026-09-20"}),
    ("gwprice", "https://gw.flight.qunar.com/api/f/price",
     {"dep": "杭州", "arr": "重庆", "date": "2026-09-20"}),
    ("gwlow", "https://gw.flight.qunar.com/api/f/lowPrice",
     {"dep": "杭州", "arr": "重庆", "date": "2026-09-20"}),
    ("tsearch", "https://touch.flight.qunar.com/api/touch/domestic/search",
     {"dep": "杭州", "arr": "重庆", "date": "2026-09-20"}),
]


def main():
    s = requests.Session()
    s.headers.update({"User-Agent": UA,
                      "Referer": "https://m.flight.qunar.com/h5flight/detail",
                      "Accept": "application/json"})
    for tag, url, params in CANDIDATES:
        try:
            r = s.get(url, params=params, timeout=15)
            ct = r.headers.get("Content-Type", "")
            body = r.text[:220].replace("\n", " ")
            print("{} -> {} ct={} body={}".format(tag, r.status_code, ct, body))
        except Exception as e:
            print(tag, "ERR", str(e)[:120])
        time.sleep(1.0)


if __name__ == "__main__":
    main()
