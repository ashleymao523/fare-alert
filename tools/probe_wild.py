#!/usr/bin/env python3
"""Last-round probes: gateway endpoint names + intl calendar variants."""
import requests

GW = "https://gw.flight.qunar.com/api/f/"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
H = {"User-Agent": UA, "Referer": "https://m.flight.qunar.com/",
     "Accept": "application/json"}

NAMES = ["recommendLowPrice", "specialOffer", "lowPriceCalendar", "price",
         "lowPrice", "cheapCalendar", "cheapFlight", "promoCalendar",
         "intlPriceCalendar", "intlCalendar"]


def probe_gw():
    for n in NAMES:
        try:
            r = requests.get(GW + n, params={"dep": "杭州", "arr": "重庆",
                                             "date": "2026-09-20"},
                             headers=H, timeout=12)
            ct = r.headers.get("Content-Type", "")
            body = r.text[:100].replace("\n", " ")
            print("gw/{} -> {} {} {}".format(n, r.status_code, ct[:24], body))
        except Exception as e:
            print("gw/{} ERR {}".format(n, str(e)[:80]))


def probe_intl():
    variants = [
        ("iata", "HGH", "BKK"),
        ("en", "Hangzhou", "Bangkok"),
        ("cn", "杭州", "曼谷"),
        ("cn2", "杭州", "香港"),
    ]
    for tag, dep, arr in variants:
        try:
            r = requests.get(GW + "priceCalendar",
                             params={"dep": dep, "arr": arr, "days": "",
                                     "priceType": "1"}, headers=H, timeout=15)
            j = r.json()
            code = (j.get("bstatus") or {}).get("code")
            fl = (j.get("data") or {}).get("gflights") or []
            priced = [e for e in fl if e.get("price")]
            dates = [e["date"] for e in priced][:8]
            print("intl {} dep={} arr={} code={} rows={} priced={} sample={}".format(
                tag, dep, arr, code, len(fl), len(priced), ",".join(dates)))
        except Exception as e:
            print("intl {} ERR {}".format(tag, str(e)[:80]))


def probe_roundtrip():
    variants = [
        ("rt_backDate", {"dep": "杭州", "arr": "重庆", "days": "",
                         "priceType": "1", "backDate": "2026-09-27"}),
        ("rt_fromto", {"dep": "杭州", "arr": "重庆", "days": "",
                       "priceType": "1", "fromDate": "2026-09-20",
                       "toDate": "2026-10-20"}),
        ("rt_goDate", {"dep": "杭州", "arr": "重庆", "days": "",
                       "priceType": "1", "goDate": "2026-09-20"}),
    ]
    for tag, p in variants:
        try:
            j = requests.get(GW + "priceCalendar", params=p, headers=H,
                             timeout=15).json()
            fl = (j.get("data") or {}).get("gflights") or []
            priced = [e for e in fl if e.get("price")]
            print("{} rows={} priced={} first_priced={}".format(
                tag, len(fl), len(priced),
                (priced[0] if priced else {}).get("date")))
        except Exception as e:
            print(tag, "ERR", str(e)[:80])
        except Exception as e:
            print(tag, "ERR", str(e)[:80])
        except Exception as e:
            print("intl {} ERR {}".format(tag, str(e)[:80]))


if __name__ == "__main__":
    import sys
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    if only in ("rt", "all"):
        probe_roundtrip()
    if only in ("intl", "all"):
        probe_intl()
    if only in ("gw", "all"):
        probe_gw()
