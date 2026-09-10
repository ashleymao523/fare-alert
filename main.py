# -*- coding: utf-8 -*-
"""FareAlert: monitor lowest flight fares (tax-included) vs student train fares."""
import argparse
import bisect
import datetime as dt
import json
import logging
import os
import random
import sys
import time

import requests

from core.alerts import build_message, evaluate, tax_amount, total_price
from core.config import load_config
from core.crawl import CrawlRecorder
from core.flights import (airline_name, booking_url, estimate_duration_text,
                          fetch_calendar, fetch_intl_promo_calendar,
                          merge_fill_deals, window_dates)
from core.intl import city_iata, fetch_intl_calendar, fetch_schedule_times
from core.models import FlightDeal
from core.notify import has_channel, push_all
from core.report import write_report
from core.sched_board import (board_lookup, load_sched_db, touches_hangzhou,
                              update_sched_db)
from core.state import load_state, save_state
from core.trains import refresh_train_info

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

FILL_CACHE_FILE = "amadeus_fill_cache.json"
FILL_CACHE_TTL = 86400  # gap-fill needs daily freshness, not per-poll
NON_REAL_SOURCES = ("nearby-ref", "interp")


def setup_logging():
    try:  # GBK console pipes crash on CJK/¥ without lenient errors
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    log = logging.getLogger("fare-alert")
    if log.handlers:
        return log
    os.makedirs(DATA_DIR, exist_ok=True)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(os.path.join(DATA_DIR, "run.log"), encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(sh)
    return log


def make_session(cfg):
    s = requests.Session()
    s.trust_env = bool(cfg.get("network", {}).get("trust_env", False))
    return s


def _flight_dict(route, deal, cfg, alert_dates):
    tax_cfg = cfg.get("tax", {})
    bag = cfg.get("baggage_policy", {})
    code = deal.airline_code
    total = total_price(deal.bare_price, tax_cfg)
    if deal.source == "amadeus-intl":
        airline = "国际含税最低价(Amadeus)"
        bag_default = "国际线托运额度以航司舱位为准"
    elif deal.source == "qunar-intl":
        airline = "国际特价(去哪儿日历)"
        bag_default = "国际线托运额度以航司舱位为准"
    elif deal.source == "amadeus-fill":
        airline = "Amadeus缺价补全(含税)"
        bag_default = "以购票页为准"
    elif deal.source == "nearby-ref":
        airline = "临近日参考价"
        bag_default = "以购票页为准"
    elif deal.source == "interp":
        airline = "两侧真实价插值(估)"
        bag_default = "以购票页为准"
    else:
        airline = airline_name(code)
        bag_default = "以购票页为准"
    return {
        "date": deal.date,
        "bare_price": deal.bare_price,
        "total_price": total,
        "flight_no": deal.flight_no,
        "airline": airline,
        "airline_code": code,
        "baggage": bag.get(code, bag_default),
        "below": total < route.get("threshold_total", 500),
        "alert": deal.date in alert_dates,
        "url": deal.url,
        "dep_time": deal.dep_time,
        "arr_time": deal.arr_time,
        "duration_text": deal.duration_text,
        "time_src": deal.time_src,
        "source": deal.source,
        "ref_offset": deal.ref_offset if deal.source == "nearby-ref" else 0,
    }


FILL_ENABLED_DFT = True


def _fill_reference_deals(deals, date_from, date_to, fc, tc,
                          max_days=7, max_days_far=45):
    """Attach nearest-priced-date reference deals for gap dates.

    The qunar calendar cache leaves some dates unpriced ("查价"); those need a
    per-date search that requires a session, which we do not bypass. Instead we
    mirror the nearest priced date as a clearly-badged display-only reference
    so the calendar has no blank cells: tight refs within max_days, extended
    refs within max_days_far when the source has no price at all in the tail
    (e.g. inventory not loaded yet). ref_offset carries the distance so the UI
    can label staleness. Reference deals never trigger alerts and never win
    cheapest/KPI computations.
    """
    real = [d for d in deals if d.source not in NON_REAL_SOURCES]
    if not real:
        return deals
    have = {d.date for d in deals}
    gaps = [x for x in window_dates(date_from, date_to) if x not in have]
    if not gaps:
        return deals
    by_date = {d.date: d for d in real}
    dates_sorted = sorted(by_date)
    refs = []
    max_interp_span = 14  # interp only between two real prices <= 14d apart
    for g in gaps:
        gd = dt.date.fromisoformat(g)
        # Two-sided neighbor interpolation first (clearly badged, display-only)
        i = bisect.bisect_left(dates_sorted, g)
        left = dates_sorted[i - 1] if i > 0 else None
        right = dates_sorted[i] if i < len(dates_sorted) else None
        if left and right:
            dl = (gd - dt.date.fromisoformat(left)).days
            dr = (dt.date.fromisoformat(right) - gd).days
            if dl + dr <= max_interp_span:
                lo, hi = by_date[left], by_date[right]
                w = dl / float(dl + dr)
                price = int(round(
                    (lo.bare_price * w + hi.bare_price * (1.0 - w)) / 10.0) * 10)
                near = lo if dl <= dr else hi
                refs.append(FlightDeal(
                    date=g, bare_price=price, flight_no=near.flight_no,
                    dep_time=near.dep_time, arr_time=near.arr_time,
                    duration_text=near.duration_text, time_src=near.time_src,
                    source="interp", url=booking_url(fc, tc, g),
                    ref_offset=0))
                continue
        # Fall back to the nearest priced date as a reference
        best_d, best_delta = None, None
        for rd in dates_sorted:
            delta = abs((dt.date.fromisoformat(rd) - gd).days)
            if best_delta is None or delta < best_delta:
                best_d, best_delta = rd, delta
        if best_d is None or best_delta > max_days_far:
            continue
        src = by_date[best_d]
        refs.append(FlightDeal(
            date=g, bare_price=src.bare_price, flight_no="",
            source="nearby-ref", url=booking_url(fc, tc, g),
            ref_offset=best_delta))
    return deals + refs


def _cached_amadeus_fill(session, net, cfg, ama_cfg, fi, ti,
                         date_from, date_to, data_dir):
    """Amadeus cheapest-calendar with a 24h file cache to protect quota."""
    key = "{}-{}-{}-{}".format(fi, ti, date_from, date_to)
    path = os.path.join(data_dir, FILL_CACHE_FILE)
    now = time.time()
    cache = {}
    try:
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
        ent = cache.get(key)
        if ent and now - float(ent.get("ts", 0)) < FILL_CACHE_TTL:
            return [FlightDeal(date=d[0], bare_price=d[1], flight_no="",
                               source="amadeus-fill") for d in ent.get("deals", [])]
    except Exception:
        cache = {}
    deals = fetch_intl_calendar(session, net, ama_cfg, cfg.get("tax", {}),
                                fi, ti, date_from, date_to, data_dir)
    try:
        cache[key] = {"ts": now, "deals": [[d.date, d.bare_price] for d in deals]}
        os.makedirs(data_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass
    return deals


def _fetch_route_flights(session, net, route, date_from, date_to,
                         cfg, ama_cfg, ama_ready, direction="out",
                         rec=None, route_id=""):
    """Fetch one leg's calendar. direction 'out'/'ret' swaps the cities."""
    if direction == "ret":
        fc, tc = route.get("to_city", ""), route.get("from_city", "")
        fi, ti = route.get("to_iata", ""), route.get("from_iata", "")
    else:
        fc, tc = route.get("from_city", ""), route.get("to_city", "")
        fi, ti = route.get("from_iata", ""), route.get("to_iata", "")
    if route.get("intl"):
        # 1) Amadeus full calendar when key ready (richer coverage)
        deals = []
        enabled = ((cfg.get("sources") or {}).get("enabled") or {})
        if ama_ready and enabled.get("amadeus-intl", True):
            try:
                deals = fetch_intl_calendar(session, net, ama_cfg,
                                            cfg.get("tax", {}),
                                            fi, ti, date_from, date_to, DATA_DIR)
            except Exception as e:
                if rec:
                    rec.step("amadeus-intl", route_id, "fetch calendar",
                             "error", 0, error=e)
        # 2) keyless qunar intl promo floor prices (sparse, always merged)
        t0p = time.time()
        try:
            promo = fetch_intl_promo_calendar(session, net, fc, tc,
                                              date_from, date_to,
                                              cfg.get("tax", {}))
            have = {d.date for d in deals}
            keep = [d for d in promo if d.date not in have]
            deals.extend(keep)
            deals.sort(key=lambda x: (x.bare_price, x.date))
            if rec:
                rec.step("qunar-intl", route_id, "intl promo calendar", "ok",
                         (time.time() - t0p) * 1000, count=len(promo))
        except Exception as e:
            if rec:
                rec.step("qunar-intl", route_id, "intl promo calendar", "error",
                         (time.time() - t0p) * 1000, error=e)
            if not deals:
                raise
        return deals
    deals = fetch_calendar(session, net, fc, tc, date_from, date_to)

    # ---- gap-fill: qunar calendar holes via Amadeus cheapest-dates ----
    covered = {d.date for d in deals}
    gaps = [d for d in window_dates(date_from, date_to) if d not in covered]
    if not gaps:
        return deals
    enabled = ((cfg.get("sources") or {}).get("enabled") or {})
    if not ama_ready or not enabled.get("amadeus-fill", FILL_ENABLED_DFT):
        if rec:
            rec.step("amadeus-fill", route_id, "fill gaps", "skip", 0,
                     error="缺{}天·未配Amadeus密钥".format(len(gaps)))
        return deals
    fi2 = (fi or "").strip().upper() or city_iata(fc)
    ti2 = (ti or "").strip().upper() or city_iata(tc)
    t0f = time.time()
    if not (fi2 and ti2):
        if rec:
            rec.step("amadeus-fill", route_id, "fill gaps", "skip",
                     (time.time() - t0f) * 1000,
                     error="缺{}天·无IATA映射".format(len(gaps)))
        return deals
    try:
        ama_deals = _cached_amadeus_fill(session, net, cfg, ama_cfg,
                                         fi2, ti2, date_from, date_to, DATA_DIR)
        deals, nfill = merge_fill_deals(
            deals, ama_deals, lambda d: booking_url(fc, tc, d))
        if rec:
            rec.step("amadeus-fill", route_id, "fill gaps", "ok",
                     (time.time() - t0f) * 1000, count=nfill)
    except Exception as e:
        if rec:
            rec.step("amadeus-fill", route_id, "fill gaps", "error",
                     (time.time() - t0f) * 1000, error=e)
    return deals


def _enrich_flight_times(session, net, route, deals, cfg, ama_cfg,
                         ama_ready, date_from, date_to,
                         rec=None, route_id=""):
    """Fill duration estimates (great-circle, labeled) + real dep/arr times
    via Amadeus schedules (best-effort, 24h cached, only when key present)."""
    if not deals:
        return deals
    fc, tc = route.get("from_city", ""), route.get("to_city", "")
    fi = (route.get("from_iata") or "").strip().upper() or city_iata(fc)
    ti = (route.get("to_iata") or "").strip().upper() or city_iata(tc)
    by_no = {}
    if ama_ready and fi and ti and any(d.flight_no for d in deals):
        t0 = time.time()
        try:
            rows = fetch_schedule_times(session, net, ama_cfg, fi, ti,
                                        date_from, date_to, DATA_DIR)
            by_no = {r["n"].upper(): r for r in rows if r.get("n")}
            if rec:
                rec.step("amadeus-times", route_id, "schedule lookup", "ok",
                         (time.time() - t0) * 1000, count=len(rows),
                         cached=bool(rows))
        except Exception as e:
            if rec:
                rec.step("amadeus-times", route_id, "schedule lookup", "skip",
                         (time.time() - t0) * 1000, error=e)
    # v0.18: zero-key airport-board fallback (see core/sched_board.py).
    # Amadeus rows win; the board only fills what Amadeus could not.
    bdb = load_sched_db(DATA_DIR)
    t0b = time.time()
    n_board = 0
    for d in deals:
        no = (d.flight_no or "").strip()
        if "/" in no:  # connecting itinerary: estimate with layover
            segs = [s.strip().upper() for s in no.split("/") if s.strip()]
            seg_rows = [by_no.get(s) for s in segs]
            if seg_rows and seg_rows[0] and seg_rows[0].get("dep"):
                d.dep_time = seg_rows[0]["dep"]
                d.time_src = "amadeus"
            if seg_rows and seg_rows[-1] and seg_rows[-1].get("arr"):
                d.arr_time = seg_rows[-1]["arr"]
                d.time_src = "amadeus"
            if not d.dep_time and segs:
                ent = board_lookup(bdb, segs[0], d.date, fc, "")
                if ent and ent.get("dep"):
                    d.dep_time = ent["dep"]
                    d.time_src = "airport-board"
                    n_board += 1
            if not d.arr_time and segs:
                ent = board_lookup(bdb, segs[-1], d.date, "", tc)
                if ent and ent.get("arr"):
                    d.arr_time = ent["arr"]
                    if d.time_src != "amadeus":
                        d.time_src = "airport-board"
                    n_board += 1
            if not d.duration_text:
                d.duration_text = estimate_duration_text(fi, ti, connecting=True)
            continue
        row = by_no.get(no.upper())
        if row:
            d.dep_time = row.get("dep") or d.dep_time
            d.arr_time = row.get("arr") or d.arr_time
            d.duration_text = row.get("dur") or d.duration_text
            if d.dep_time or d.arr_time:
                d.time_src = "amadeus"
        if no and not (d.dep_time and d.arr_time):
            ent = board_lookup(bdb, no, d.date, fc, tc)
            if ent:
                got = False
                if not d.dep_time and ent.get("dep"):
                    d.dep_time = ent["dep"]
                    got = True
                if not d.arr_time and ent.get("arr"):
                    d.arr_time = ent["arr"]
                    got = True
                if got:
                    n_board += 1
                    if d.time_src != "amadeus":
                        d.time_src = "airport-board"
        if not d.duration_text:
            d.duration_text = estimate_duration_text(fi, ti)
    if rec and (n_board or not ama_ready):
        rec.step("hgh-board-times", route_id, "board time fallback", "ok",
                 (time.time() - t0b) * 1000, count=n_board)
    return deals


def run_once(cfg, log, push_enabled=True, verbose=False, trigger="cli"):
    """One full cycle. Returns snapshot dict (also written to data/snapshot.json)."""
    rec = CrawlRecorder(DATA_DIR)
    rec.begin(trigger=trigger)
    session = make_session(cfg)
    net = cfg.get("network", {})
    state = load_state(os.path.join(DATA_DIR, "state.json"))
    today = dt.date.today()
    enabled = (cfg.get("sources") or {}).get("enabled") or {}
    use_flight = enabled.get("qunar-calendar", True)
    use_train = enabled.get("12306-train", True)
    if enabled.get("hgh-board-times", True):
        t0b = time.time()
        if not touches_hangzhou(cfg.get("routes")):
            # board data only serves HGH routes: skip, save request budget
            rec.step("hgh-board-times", "sched-db",
                     "update flight time db", "skip", 0,
                     error="no route touches Hangzhou(HGH) board")
        else:
            try:
                update_sched_db(session, net, DATA_DIR, log)
                rec.step("hgh-board-times", "sched-db",
                         "update flight time db", "ok", (time.time() - t0b) * 1000)
            except Exception as e:
                log.warning("airport board update failed: %s" % e)
                rec.step("hgh-board-times", "sched-db",
                         "update flight time db", "skip",
                         (time.time() - t0b) * 1000, error=e)
    snapshot_routes = []
    pending_push = []

    for route in cfg.get("routes", []):
        date_from = (today + dt.timedelta(days=1)).isoformat()
        date_to = (today + dt.timedelta(days=int(route.get("window_days", 60)))).isoformat()
        trip_type = "roundtrip" if route.get("trip_type") == "roundtrip" else "oneway"
        intl = bool(route.get("intl"))
        ama_cfg = ((cfg.get("sources") or {}).get("amadeus")) or {}
        ama_ready = bool((ama_cfg.get("client_id") or "").strip()
                         and (ama_cfg.get("client_secret") or "").strip())
        flight_key = (("amadeus-intl" if ama_ready else "qunar-intl")
                      if intl else "qunar-calendar")
        use_leg_flight = use_flight and (
            not intl or enabled.get("amadeus-intl", True)
            or enabled.get("qunar-intl", True))
        route_snap = {
            "id": route.get("id", "route"),
            "from_city": route.get("from_city", ""),
            "to_city": route.get("to_city", ""),
            "from_iata": (route.get("from_iata") or "").strip().upper(),
            "to_iata": (route.get("to_iata") or "").strip().upper(),
            "window_days": int(route.get("window_days", 60)),
            "threshold_total": route.get("threshold_total", 500),
            "trip_type": trip_type,
            "intl": intl,
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "window": [date_from, date_to],
            "deals": [],
            "return_deals": [],
            "combined": None,
            "combined_by_date": {},
            "train": None,
            "days_below": 0,
            "cheapest_total": None,
            "flight_source_status": "ok",
        }

        deals, return_deals = [], []
        if not use_leg_flight:
            route_snap["flight_source_status"] = "disabled"
            rec.step(flight_key, route_snap["id"], "fetch calendar", "disabled", 0)
            log.info("[{}] flight source disabled, skip".format(route_snap["id"]))
        else:
            t0 = time.time()
            try:
                deals = _fetch_route_flights(session, net, route, date_from,
                                             date_to, cfg, ama_cfg, ama_ready, "out",
                                             rec, route_snap["id"])
                deals = _enrich_flight_times(session, net, route, deals, cfg,
                                             ama_cfg, ama_ready, date_from, date_to,
                                             rec, route_snap["id"])
                deals = _fill_reference_deals(
                    deals, date_from, date_to,
                    route.get("from_city", ""), route.get("to_city", ""))
                rec.step(flight_key, route_snap["id"], "fetch calendar", "ok",
                         (time.time() - t0) * 1000, count=len(deals))
            except Exception as e:
                rec.step(flight_key, route_snap["id"], "fetch calendar", "error",
                         (time.time() - t0) * 1000, error=e)
                route_snap["flight_source_status"] = "error: " + str(e)[:120]
                log.error("flight fetch failed [{}]: {}".format(route_snap["id"], e))
            if trip_type == "roundtrip" and deals:
                t0r = time.time()
                try:
                    return_deals = _fetch_route_flights(session, net, route,
                                                        date_from, date_to, cfg,
                                                        ama_cfg, ama_ready, "ret",
                                                        rec, route_snap["id"])
                    return_deals = _enrich_flight_times(
                        session, net, route, return_deals, cfg, ama_cfg,
                        ama_ready, date_from, date_to, rec, route_snap["id"])
                    return_deals = _fill_reference_deals(
                        return_deals, date_from, date_to,
                        route.get("to_city", ""), route.get("from_city", ""))
                    rec.step(flight_key, route_snap["id"], "fetch return calendar",
                             "ok", (time.time() - t0r) * 1000, count=len(return_deals))
                except Exception as e:
                    rec.step(flight_key, route_snap["id"], "fetch return calendar",
                             "error", (time.time() - t0r) * 1000, error=e)
                    route_snap["flight_source_status"] = "error: 返程获取失败 " + str(e)[:90]
                    log.error("return flight fetch failed [{}]: {}".format(route_snap["id"], e))
                    return_deals = []

        train_info = None
        if use_train and (route.get("train_compare") or {}).get("enabled"):
            t1 = time.time()
            try:
                train_info = refresh_train_info(session, net, route, DATA_DIR)
                n_trains = 0
                for v in (train_info.get("pairs") or {}).values():
                    if isinstance(v, list):
                        n_trains += len(v)
                rec.step("12306-train", route_snap["id"], "fetch trains", "ok",
                         (time.time() - t1) * 1000, count=n_trains,
                         cached=bool(train_info.get("from_cache")))
            except Exception as e:
                rec.step("12306-train", route_snap["id"], "fetch trains", "error",
                         (time.time() - t1) * 1000, error=e)
                log.warning("train fetch failed [{}]: {}".format(route_snap["id"], e))
        else:
            rec.step("12306-train", route_snap["id"], "fetch trains", "disabled", 0)

        real_deals = [d for d in deals if d.source not in NON_REAL_SOURCES]
        alert_deals, combined_meta, combined_by_date = real_deals, None, {}
        if trip_type == "roundtrip" and deals and return_deals:
            tax_cfg = cfg.get("tax", {})
            ret_sorted = sorted(
                [d for d in return_deals
                 if d.source not in NON_REAL_SOURCES],
                key=lambda x: (x.bare_price, x.date))
            alert_deals = []
            for d1 in real_deals:
                pick = None
                for d2 in ret_sorted:
                    if d2.date > d1.date:
                        pick = d2
                        break
                if not pick:
                    continue
                t1 = total_price(d1.bare_price, tax_cfg)
                t2 = total_price(pick.bare_price, tax_cfg)
                comb = t1 + t2
                combined_by_date[d1.date] = {
                    "ret_date": pick.date, "total": comb,
                    "out_total": t1, "ret_total": t2,
                    "ret_flight": pick.flight_no,
                }
                alert_deals.append(FlightDeal(
                    date=d1.date,
                    bare_price=round(comb - tax_amount(tax_cfg), 1),
                    flight_no="去{}/返{}".format(d1.flight_no or "国际",
                                                 pick.flight_no or "国际"),
                    source=d1.source, url=d1.url))
                if combined_meta is None or comb < combined_meta["total"]:
                    combined_meta = {
                        "out_date": d1.date, "ret_date": pick.date, "total": comb,
                        "out_total": t1, "ret_total": t2,
                        "out_flight": d1.flight_no, "ret_flight": pick.flight_no,
                        "url": d1.url,
                    }
            route_snap["combined"] = combined_meta
            route_snap["combined_by_date"] = combined_by_date

        to_alert, below = [], []
        if alert_deals:
            now_ts = time.time()
            to_alert, below = evaluate(route, alert_deals, state, cfg, now_ts,
                                       record=push_enabled)
            try:
                write_report(
                    cfg, route, deals, train_info, state,
                    os.path.join(DATA_DIR, "report", route_snap["id"]),
                    alert_dates={d.date for _, d in to_alert},
                )
            except Exception as e:
                log.warning("report write failed [{}]: {}".format(route_snap["id"], e))

        alert_dates = {d.date for _, d in to_alert}
        route_snap["deals"] = [_flight_dict(route, d, cfg, alert_dates) for d in deals]
        route_snap["return_deals"] = [_flight_dict(route, d, cfg, set())
                                      for d in return_deals]
        route_snap["days_below"] = len(below)
        if trip_type == "roundtrip" and combined_meta:
            route_snap["cheapest_total"] = combined_meta["total"]
            log.info("[{}] RT window {}~{} best {}+{} total ¥{} ({} days below threshold)".format(
                route_snap["id"], date_from, date_to,
                combined_meta["out_date"], combined_meta["ret_date"],
                int(route_snap["cheapest_total"]), len(below)))
        elif real_deals:
            route_snap["cheapest_total"] = total_price(real_deals[0].bare_price, cfg.get("tax", {}))
            log.info("[{}] window {}~{} cheapest {} {} total ¥{} ({} days below threshold)".format(
                route_snap["id"], date_from, date_to,
                deals[0].date, deals[0].flight_no,
                int(route_snap["cheapest_total"]), len(below)))
        route_snap["train"] = train_info
        if verbose:
            for d in deals[:15]:
                log.info("   {} {} {} bare ¥{} total ¥{}".format(
                    d.date, d.flight_no, airline_name(d.airline_code),
                    int(d.bare_price), int(total_price(d.bare_price, cfg.get("tax", {})))))
        snapshot_routes.append(route_snap)
        if to_alert:
            pending_push.append((route, to_alert, below, train_info))

    snapshot = {
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "routes": snapshot_routes,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)

    pushed = 0
    if push_enabled:
        save_state(os.path.join(DATA_DIR, "state.json"), state)
        for route, to_alert, below, train_info in pending_push:
            title, body = build_message(route, to_alert, below, train_info, cfg)
            log.info("ALERT >> " + title)
            push_all(cfg, log, title, body,
                     url=to_alert[0][1].url, route_id=route.get("id"))
            pushed += len(to_alert)
        if pending_push:
            rec.step("push", "all", "send alerts", "ok", 0, count=pushed)
    rec.finish({
        "routes": len(snapshot_routes),
        "deals": sum(len(r["deals"]) for r in snapshot_routes),
        "days_below": sum(r["days_below"] for r in snapshot_routes),
        "pushed": pushed,
    })
    try:  # M2: per-source health score / degrade flag / diagnose (never block main flow)
        from core.health import update_from_crawl
        update_from_crawl(DATA_DIR)
    except Exception:
        log.exception("health update failed")
    try:  # M4: daily KPI archive + optional weekly digest push
        from core.history import append_history
        from core.weekly import (build_weekly, mark_failed, mark_pushed,
                                 should_push)
        hist_path = os.path.join(DATA_DIR, "history.json")
        append_history(snapshot, hist_path)
        wk_path = os.path.join(DATA_DIR, "weekly_push.json")
        if push_enabled and should_push(cfg, wk_path):
            if not has_channel(cfg):
                log.warning("weekly push skipped: no push channel configured "
                            "(timer not consumed)")
            else:
                report = build_weekly(hist_path)
                if report.get("ok"):
                    results = push_all(cfg, log, "📈 FareAlert 价格周报",
                                       report["text"], url="")
                    failed = [x for x in results if ":ERR" in x]
                    if len(failed) == len(results):
                        # every channel failed: retry in 6h, no 45min storm
                        mark_failed(wk_path)
                        log.warning("weekly push failed on all channels, "
                                    "will retry in 6h: " + "; ".join(failed))
                    else:
                        if failed:  # partial success still consumes the timer
                            log.warning("weekly push partial failure "
                                        "(timer consumed): " + "; ".join(failed))
                        mark_pushed(wk_path)
                        log.info("weekly report pushed")
    except Exception:
        log.exception("weekly history/report failed")
    return snapshot


def main():
    ap = argparse.ArgumentParser(description="fare alert component")
    ap.add_argument("--once", action="store_true", help="run one cycle then exit")
    ap.add_argument("--loop", action="store_true", help="run forever with interval+jitter")
    ap.add_argument("--query", action="store_true", help="print cheapest table, no push")
    ap.add_argument("--test-push", action="store_true", help="send a test push message")
    args = ap.parse_args()

    log = setup_logging()
    cfg = load_config(CONFIG_PATH)

    if args.test_push:
        push_all(cfg, log, "✈️FareAlert 测试推送", "配置成功!这是测试消息。", url="")
        return
    if args.query:
        run_once(cfg, log, push_enabled=False, verbose=True)
        return
    if args.loop:
        interval = int(cfg.get("schedule", {}).get("interval_minutes", 45)) * 60
        jitter = int(cfg.get("schedule", {}).get("jitter_minutes", 10)) * 60
        while True:
            try:
                run_once(cfg, log)
            except Exception as e:
                log.error("cycle error: " + str(e))
            time.sleep(interval + random.randint(0, jitter))
        return
    run_once(cfg, log)


if __name__ == "__main__":
    main()
