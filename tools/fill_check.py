# -*- coding: utf-8 -*-
"""Gap-fill logic checks (no network needed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.flights import merge_fill_deals, window_dates
from core.intl import city_iata
from core.models import FlightDeal

ok = 0


def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    if cond:
        ok += 1
    else:
        raise SystemExit(1)


# window_dates covers inclusive range
days = window_dates("2026-09-09", "2026-09-11")
check("window_dates inclusive", days == ["2026-09-09", "2026-09-10", "2026-09-11"])

# merge: only gap dates taken, source/url rewritten, sorted by price
qunar = [
    FlightDeal(date="2026-09-09", bare_price=300.0, flight_no="GS6582"),
    FlightDeal(date="2026-09-10", bare_price=350.0, flight_no="PN6436"),
]
ama = [
    FlightDeal(date="2026-09-10", bare_price=280.0, flight_no="",
               source="amadeus-intl"),  # covered date -> must be ignored
    FlightDeal(date="2026-09-20", bare_price=310.0, flight_no="",
               source="amadeus-intl"),  # gap date -> filled
    FlightDeal(date="2026-09-21", bare_price=290.0, flight_no="",
               source="amadeus-intl"),  # gap date -> filled
]
merged, nfill = merge_fill_deals(qunar, ama, lambda d: "URL_" + d)
check("fill count = 2", nfill == 2)
check("merged len = 4", len(merged) == 4)
check("filled source tagged", all(d.source == "amadeus-fill" for d in merged if d.date in ("2026-09-20", "2026-09-21")))
check("qunar deals keep source", all(d.source == "qunar-calendar" for d in merged if d.date in ("2026-09-09", "2026-09-10")))
check("filled url rewritten", [d.url for d in merged if d.date == "2026-09-20"] == ["URL_2026-09-20"])
check("price sorted", [d.bare_price for d in merged] == [290.0, 300.0, 310.0, 350.0])

# city -> IATA mapping
check("HGH", city_iata("杭州") == "HGH")
check("CKG with shi suffix", city_iata("重庆市") == "CKG")
check("unknown city -> None", city_iata("不存在城") is None)

print("fill_check all OK ({})".format(ok))
