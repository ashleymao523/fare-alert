# -*- coding: utf-8 -*-
"""v1.30: cabin precision unification + trains multi-route cache.

The v0.42-v1.29 layout kept TWO history routes per real leg (booking
patrol wrote patrol-*, qunar captures wrote point-*), so a 4487
booking estimate sat beside the real 1200 qunar price and the
threshold check ran per duplicate. v1.30 merges everything into one
canonical leg-* route, tags every observation with its source and
never lets an estimate overwrite a precise row; estimate-only dates
become precision gaps the CDP capture now hunts at double cadence.
The pending trains v4 multi-route cache rides along in this round."""
import datetime as dt
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_SRC = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
CDP_SRC = open(os.path.join(ROOT, "core", "cdp_cabin.py"),
               encoding="utf-8").read()


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name +
          (" " + str(extra) if extra else ""))
    return bool(cond)


def main():
    ok = True
    from core import cabin_monitor as cm

    # 1. precise-wins dedup inside record_low
    h = {"routes": {}}
    cm.record_low(h, "leg-A-B", "A", "B", "business",
                  "2026-10-01", 4487.0, fno="CA1", source="booking")
    e = cm.record_low(h, "leg-A-B", "A", "B", "business",
                      "2026-10-01", 1200.0, fno="CA1", source="qunar")
    obs = h["routes"]["leg-A-B"]["obs"]
    ok &= check("qunar replaces booking same flight",
                len(obs) == 1 and obs[0]["price"] == 1200.0
                and obs[0]["src"] == "qunar", obs)
    ok &= check("replaced row tagged record (undercut prior)",
                bool(e.get("record")))
    e2 = cm.record_low(h, "leg-A-B", "A", "B", "business",
                       "2026-10-01", 999.0, fno="CA1", source="booking")
    obs = h["routes"]["leg-A-B"]["obs"]
    ok &= check("booking estimate never overwrites precise",
                len(obs) == 1 and obs[0]["price"] == 1200.0,
                obs[0])
    ok &= check("rejected estimate returns incumbent (no record)",
                not e2.get("record") and e2["price"] == 1200.0)

    # 2. migration merges legacy duplicates into leg-*
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "cabin_history.json")
    legacy = {"routes": {
        "point-A-B": {"from_city": "A", "to_city": "B", "obs": [
            {"date": "2026-10-02", "cabin": "business",
             "price": 890.0, "fno": "KN1", "dep": "16:30",
             "arr": "18:40", "ts": "2026-09-18T10:00"}],
            "lowest": 890.0},
        "patrol-A-B": {"from_city": "A", "to_city": "B", "obs": [
            {"date": "2026-10-02", "cabin": "business",
             "price": 1637.9, "fno": "KN1", "ts": "2026-09-17T09:00"},
            {"date": "2026-10-03", "cabin": "business",
             "price": 1500.0, "fno": "MU2", "ts": "2026-09-17T09:30"}],
            "lowest": 1500.0},
    }}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(legacy, f, ensure_ascii=False)
    h2 = cm.load_history(tmp)
    keys = sorted(h2["routes"])
    ok &= check("legacy routes merge to one leg-*",
                keys == ["leg-A-B"], keys)
    leg = h2["routes"]["leg-A-B"]
    ok &= check("precise-wins on merge (890 kept over 1637.9)",
                leg["lowest"] == 890.0 and len(leg["obs"]) == 2,
                leg["obs"])
    srcs = {o["fno"]: o.get("src") for o in leg["obs"]}
    ok &= check("migration stamps src by origin prefix",
                srcs.get("KN1") == "qunar"
                and srcs.get("MU2") == "booking", srcs)
    with open(path, encoding="utf-8") as f:
        persisted = json.load(f)
    ok &= check("migration persisted (no point-/patrol- left)",
                "leg-A-B" in persisted["routes"]
                and not any(k.startswith(("point-", "patrol-"))
                            for k in persisted["routes"]))
    h2b = cm.load_history(tmp)
    ok &= check("migration idempotent",
                sorted(h2b["routes"]) == ["leg-A-B"])

    # 3. estimate-only dates are precision gaps
    h3 = {"routes": {"leg-A-B": {"from_city": "A", "to_city": "B",
                                 "obs": [
        {"date": "2026-10-05", "cabin": "business", "price": 1000.0,
         "fno": "CZ3", "dep": "08:00", "arr": "10:30", "ts":
         "2026-09-18T08:00", "src": "booking"},
        {"date": "2026-10-06", "cabin": "business", "price": 900.0,
         "fno": "CZ4", "dep": "09:00", "arr": "11:30", "ts":
         "2026-09-18T08:00", "src": "qunar"},
        {"date": "2026-10-07", "cabin": "business", "price": 950.0,
         "fno": "CZ5", "dep": "10:00", "arr": "12:30", "ts":
         "2026-09-18T08:00"},
     ], "lowest": 900.0}}}
    gaps = cm.time_gap_dates(h3, "leg-A-B", "2026-10-05", "2026-10-07")
    ok &= check("estimate-only date flagged, precise + legacy not",
                gaps == ["2026-10-05"], gaps)
    pr = cm.probe_dates(h3, "leg-A-B", "2026-10-05", "2026-10-08", k=2)
    ok &= check("probe rotation prefers the precision gap",
                "2026-10-05" in pr and pr[0] == "2026-10-05", pr)

    # 4. board/timetable expose precision fields
    b = cm.history_board(h3)[0]
    ok &= check("board row has low_src + precise count",
                b.get("low_src") == "qunar" and b.get("precise") == 1,
                b)
    t = cm.history_timetable(h3)[0]
    ok &= check("timetable group precise chip present",
                t.get("precise") == 1, t.get("precise"))
    ok &= check("timetable rows carry src",
                all("src" in r for r in t["rows"]))

    # 5. cdp patrol_fill hunts precision gaps under leg-* keys
    import core.cdp_cabin as cc
    day = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    h4 = {"routes": {"leg-A-B": {"from_city": "A", "to_city": "B",
                                 "obs": [
        {"date": day, "cabin": "business", "price": 1000.0,
         "fno": "CZ9", "dep": "08:00", "arr": "10:30", "ts":
         "2026-09-18T08:00", "src": "booking"}],
        "lowest": 1000.0}}}
    tmp4 = tempfile.mkdtemp()
    with open(os.path.join(tmp4, "cabin_history.json"), "w",
              encoding="utf-8") as f:
        json.dump(h4, f, ensure_ascii=False)
    seen = {}

    def fake_capture(net_cfg, data_dir, targets, log=None, **kw):
        seen["targets"] = targets
        return len(targets)

    orig = cc.capture_batch
    cc.capture_batch = fake_capture
    try:
        info = cc.patrol_fill(
            {"enabled": True, "watch_from_cities": ["A"],
             "to_cities": ["B"], "cdp_capture": True}, [], tmp4,
            throttle_hits=0)
    finally:
        cc.capture_batch = orig
    ok &= check("cdp targets include the estimate-only date",
                any(t.get("date") == day
                    for t in (seen.get("targets") or [])),
                seen.get("targets"))
    ok &= check("cdp info reports stored + ledger use",
                info.get("stored") == len(seen.get("targets") or [])
                and info.get("used", 0) + info.get("targets", 0)
                == info.get("used", 0) + len(seen.get("targets") or []),
                info)
    with open(os.path.join(tmp4, "cdp_cabin_ledger.json"),
              encoding="utf-8") as f:
        led = json.load(f)
    ok &= check("ledger counts today's captures",
                int((led.get("days") or {}).get(
                    dt.date.today().isoformat()) or 0)
                == len(seen.get("targets") or []), led.get("days"))

    # 6. accelerated capture parameters + wiring
    ok &= check("cadence every 2nd round", "(rnd % 2) != 1" in CDP_SRC)
    ok &= check("default k raised to 4",
                'or 4)' in CDP_SRC and "cdp_dates_per_round" in CDP_SRC)
    ok &= check("default daily cap raised to 24",
                'or 24)' in CDP_SRC
                and "cdp_capture_daily_cap" in CDP_SRC)
    ok &= check("cdp gap query keyed leg-*", 'hid = "leg-' in CDP_SRC)
    ok &= check("absorb canonicalizes hid to leg-*",
                'hid = "leg-{fc}-{tc}".format(' in MAIN_SRC)
    for s in ("qunar", "booking", "amadeus"):
        ok &= check("main.py passes source=" + s,
                    'source="' + s + '"' in MAIN_SRC)

    # 7. trains v4 multi-route cache (rides in v1.30)
    from core import trains as tr
    tmp5 = tempfile.mkdtemp()
    stations = {"S1": {"code": "S1", "pinyin": "s1", "py": "s1"},
                "S2": {"code": "S2", "pinyin": "s2", "py": "s2"}}
    tr.get_stations = lambda *a, **kw: stations
    tr.query_pair = (
        lambda sess, net, date, f, t, st:
            [tr.TrainFare(pair=f + "-" + t, train_code="G1",
                          from_station=f, to_station=t,
                          dep_time="08:00", arr_time="12:00",
                          duration_text="4h", seats={"二等座": 500.0},
                          url="https://x")])
    rc1 = {"id": "r1", "train_compare": {"station_pairs": [["S1", "S2"]]}}
    rc2 = {"id": "r2", "train_compare": {"station_pairs": [["S2", "S1"]]}}
    tr.refresh_train_info(None, {}, rc1, tmp5)
    tr.refresh_train_info(None, {}, rc2, tmp5)
    with open(os.path.join(tmp5, "train_cache.json"),
              encoding="utf-8") as f:
        tc = json.load(f)
    ok &= check("v4 cache keeps BOTH routes",
                tc.get("v") == 4
                and set((tc.get("routes") or {})) == {"r1", "r2"},
                sorted((tc.get("routes") or {})))
    again = tr.refresh_train_info(None, {}, rc1, tmp5)
    ok &= check("route r1 hits cache (no refetch)",
                again.get("from_cache") is True)
    forced = tr.refresh_train_info(None, {}, rc1, tmp5, force=True)
    ok &= check("force=True bypasses cache",
                forced.get("from_cache") is False)

    print("v1.30 checks: %s" % ("all pass" if ok else "FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
