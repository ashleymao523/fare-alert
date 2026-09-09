#!/usr/bin/env python3
"""Compare empty-price date sets across priceType variants."""
import datetime
import requests

URL = "https://gw.flight.qunar.com/api/f/priceCalendar"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
H = {"User-Agent": UA, "Referer": "https://m.flight.qunar.com/",
     "Accept": "application/json"}


def fetch(dep, arr, ptype):
    r = requests.get(URL, params={"dep": dep, "arr": arr, "days": "",
                                  "priceType": ptype}, headers=H, timeout=20)
    j = r.json()
    fl = (j.get("data") or {}).get("gflights") or []
    priced = {e["date"]: float(e["price"]) for e in fl
              if e.get("date") and e.get("price")}
    return priced


def main():
    dep, arr = "杭州", "重庆"
    sets = {}
    for pt in ("0", "1", "2"):
        sets[pt] = fetch(dep, arr, pt)
        print("priceType={} priced_dates={}".format(pt, len(sets[pt])))
    for a in ("0", "1", "2"):
        for b in ("1", "2"):
            if a < b:
                only_a = set(sets[a]) - set(sets[b])
                only_b = set(sets[b]) - set(sets[a])
                print("only in ptype{}: {} dates; only in ptype{}: {} dates".format(
                    a, len(only_a), b, len(only_b)))
    merged = {}
    for pt in ("0", "1", "2"):
        for d, p in sets[pt].items():
            if d not in merged or p < merged[d]:
                merged[d] = p
    today = datetime.date.today()
    win = [(today + datetime.timedelta(days=i)).isoformat() for i in range(1, 61)]
    covered = sum(1 for d in win if d in merged)
    print("merged window coverage: {}/60".format(covered))


if __name__ == "__main__":
    main()
