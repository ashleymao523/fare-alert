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
from core.flights import (airline_name, booking_url, estimate_arrival_time,
                          estimate_duration_text, fetch_calendar,
                          fetch_intl_promo_calendar,
                          merge_fill_deals, time_coverage, window_dates,
                          NON_REAL_SOURCES)
from core.intl import city_iata, fetch_intl_calendar, fetch_schedule_times
from core.intl import fetch_cabin_offers, fetch_fill_offers
from core.cabin_monitor import (
    load_config as cabin_cfg_load, load_history as cabin_history_load,
    record_low as cabin_record_low, route_qualifies as cabin_route_qualifies,
    cabin_leg as cabin_watch_leg,
    evaluate_alert as cabin_evaluate_alert, cooldown_ok as cabin_cooldown_ok,
    record_alert_candidate as cabin_record_candidate,
    _atomic_write as cabin_atomic_write,
    patrol_legs as cabin_patrol_legs,
)
from core.point_fill import load_cache as load_point_cache
from core.point_fill import merge_point_fill
from core.models import FlightDeal
from core.version import CODE_VERSION
from core.notify import has_channel, push_all
from core.report import write_report
from core.sched_board import (board_lookup_x, build_route_priors,
                              flight_duration,
                              city_dep_times, city_return_dep_times,
                              load_sched_db,
                              prior_minutes_for, promote_alt_time,
                              touches_hangzhou, update_sched_db)
from core.state import load_state, save_state
from core.trains import refresh_train_info

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

FILL_CACHE_FILE = "amadeus_fill_cache.json"
FILL_CACHE_TTL = 86400  # gap-fill needs daily freshness, not per-poll


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
        "arr_est": deal.arr_est,
        "duration_text": deal.duration_text,
        "time_src": deal.time_src,
        "dep_src": deal.dep_src,
        "arr_src": deal.arr_src,
        "source": deal.source,
        "ref_offset": deal.ref_offset if deal.source == "nearby-ref" else 0,
        "alt_times": [{"no": a.get("no"), "dep": a.get("dep"),
                       "arr": a.get("arr"),
                       "airline": a.get("airline"),
                       "craft": a.get("craft"),
                       "via": a.get("via"),
                       "exact": bool(a.get("exact"))}
                      for a in (deal.alt_times or [])][:4],
        "stop_kind": deal.stop_kind,
        "stop_city": deal.stop_city,
        "stop_arr": deal.stop_arr,
    }


FILL_ENABLED_DFT = True


def _fill_reference_deals(deals, date_from, date_to, fc, tc,
                          max_days=7, max_days_far=75):
    """Attach nearest-priced-date reference deals for gap dates.

    The qunar calendar cache leaves some dates unpriced ("查价"); those need a
    per-date search that requires a session, which we do not bypass. Instead we
    mirror the nearest priced date as a clearly-badged display-only reference
    so the calendar has no blank cells: tight refs within max_days, extended
    refs within max_days_far when the source has no price at all in the tail
    (e.g. inventory not loaded yet). ref_offset carries the distance so the UI
    can label staleness. Reference deals never trigger alerts and never win
    cheapest/KPI computations.
    v0.67: radius 45->75 so a single tail anchor (qunar-intl promo often
    returns only 1-2 tail dates) still references the whole 60d window -
    the head used to stay blank when the nearest real price sat >45d away.
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


def _attach_alt_times(deals, to_city, db, from_city=None):
    """v0.26.1: reference departures for numberless gap-filled deals.

    nearby-ref/interp deals are appended AFTER _enrich_flight_times ran,
    so the v0.26 mount inside the enrich loop never saw them (Bangkok:
    48/50 deals are nearby-ref -> alt_times stayed empty in snapshots).
    Idempotent: a deal that already has a departure time is skipped.
    v0.48: a deal that carries alt_times but no dep_time gets the best
    reference departure PROMOTED onto dep_time (dep_src="alt-ref") -
    103 snapshot rows had real reference times parked in alt_times that
    the UI never lifted into the time slot. Outbound only: the board
    holds HGH departures, return legs have no matching rows.
    v0.49: pass from_city=<return origin> to attach RETURN-leg
    reference departures from the arrive board's preschtime rows
    (CITY->HGH) - the same zero-key db, still no extra request.
    v0.68: board rows carry arrival times too - the promoted reference
    now fills arr_time as well (arr_src="alt-ref", never clobbering an
    existing estimate), killing the "--:--" landing slot on intl/ref
    rows the great-circle estimator never covered."""
    ret_mode = bool(from_city and (from_city or "").strip()
                    and from_city != "杭州")
    cache = {}
    for d in deals:
        need_dep = not d.dep_time
        need_arr = not (d.arr_time or "").strip()
        if not (need_dep or need_arr):
            continue
        if not d.alt_times:
            if d.date not in cache:
                cache[d.date] = (city_return_dep_times(db, from_city, d.date)
                                 if ret_mode
                                 else city_dep_times(db, to_city, d.date))
            d.alt_times = cache[d.date]
        best = promote_alt_time(d.alt_times)
        if not best:
            continue
        if need_dep:
            d.dep_time = best["dep"]
            d.time_src = "alt-ref"
            d.dep_src = "alt-ref"
        if need_arr and (best.get("arr") or "").strip():
            d.arr_time = best["arr"]
            if not d.arr_src:
                d.arr_src = "alt-ref"
    # v0.75: real (board/promoted) dep+arr beat the great-circle
    # estimate in the duration slot; estimates keep serving rows whose
    # landing time is still unknown.
    for d in deals:
        if d.dep_time and d.arr_time and (
                not d.duration_text or "(估)" in d.duration_text):
            dur = flight_duration(d.dep_time, d.arr_time)
            if dur:
                d.duration_text = dur
    return deals


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
                         rec=None, route_id="", cabin_out=None):
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

    # v0.43: business-cabin offers BEFORE the gap-fill early-return so a
    # complete economy calendar never starves the cabin monitor (v0.42
    # bug: "if not gaps: return" skipped cabin fetch on hole-free days).
    # v0.50: cabin_leg auto-derives the watch leg - direct (to_city
    # watched) or MIRROR (from_city watched -> collect the reverse leg
    # by swapping the IATA pair, so HGH->CKG routes feed the CKG->HGH
    # business watch with zero manual reverse routes). Mirrored rows
    # must NOT join deals (wrong direction for this calendar); they
    # travel via the cabin_out list. Outbound call only - the roundtrip
    # ret call already carries the same watch leg through the out leg.
    cw = cabin_cfg_load(cfg)
    leg = cabin_watch_leg(route, cw) if direction != "ret" else None
    if leg and leg["mode"] == "mirror" and cabin_out is None:
        leg = None  # mirror rows have no channel back -> skip the fetch
    if leg:
        if leg["mode"] == "mirror":
            cfi = (ti or "").strip().upper() or city_iata(tc)
            cti = (fi or "").strip().upper() or city_iata(fc)
        else:
            cfi = (fi or "").strip().upper() or city_iata(fc)
            cti = (ti or "").strip().upper() or city_iata(tc)
        if cfi and cti:
            try:
                t0c = time.time()
                biz = fetch_cabin_offers(
                    session, net, ama_cfg, cfg.get("tax", {}),
                    cfi, cti, date_from, date_to,
                    cabin=(cw.get("cabins") or ["business"])[0],
                    data_dir=DATA_DIR)
                if leg["mode"] == "mirror" and cabin_out is not None:
                    cabin_out.extend(biz)
                else:
                    deals = deals + biz
                if rec:
                    rec.step("amadeus-cabin", route_id, "cabin offers",
                             "ok", (time.time() - t0c) * 1000,
                             count=len(biz))
            except Exception as e:
                if rec:
                    rec.step("amadeus-cabin", route_id, "cabin offers",
                             "skip", (time.time() - t0c) * 1000,
                             error="公务舱采集跳过: {}".format(e))

    # ---- gap-fill: qunar calendar holes via Amadeus cheapest-dates ----
    covered = {d.date for d in deals if (d.cabin or "") == ""}
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
    # v0.44: offer-exact last resort - dates the cheapest calendar also
    # missed get real flight offers (price + exact times + numbers),
    # cached per date for a day so the poll loop stays quota-safe.
    covered2 = {d.date for d in deals if (d.cabin or "") == ""}
    still = [d for d in gaps if d not in covered2]
    if not still:
        return deals
    t0o = time.time()
    try:
        fstats = {}
        off = _cached_fill_offers(session, net, cfg, ama_cfg,
                                  fi2, ti2, still, DATA_DIR, stats=fstats)
        if off:
            deals, _ = merge_fill_deals(
                deals, off, lambda d: booking_url(fc, tc, d))
        if rec:
            rec.step("amadeus-fill-offer", route_id, "offer fill", "ok",
                     (time.time() - t0o) * 1000, count=len(off),
                     error="缺{}天·本轮点查{}·待轮转{}".format(
                         fstats.get("holes", len(still)),
                         fstats.get("probed", 0),
                         fstats.get("deferred", 0)))
    except Exception as e:
        if rec:
            rec.step("amadeus-fill-offer", route_id, "offer fill", "skip",
                     (time.time() - t0o) * 1000, error=e)
    return deals


def _cached_fill_offers(session, net, cfg, ama_cfg, fi, ti,
                        gap_dates, data_dir, max_days=6, stats=None):
    """v0.44: offer-exact gap fill with per-date 24h cache.

    Each still-missing date costs one flight-offers call, so results
    (and negative answers) are cached per date for a day - a 45min poll
    loop stays quota-safe. Rows keep the 'amadeus-fill' source tag the
    pipeline already understands.
    v0.67: rotating budget. The old gap_dates[:max_days] truncation only
    ever probed the FIRST batch of holes - anything past #6 was starved
    forever (7 holes -> #7 never point-queried, exactly the dates users
    saw blank but could search manually). Now each round probes up to
    max_days dates whose cache entry is missing or expired; the rest
    rotate in on later rounds while fresh positives return from cache
    instantly. The negative cache doubles as the rotation cursor.
    """
    path = os.path.join(data_dir, FILL_CACHE_FILE)
    now = time.time()
    cache = {}
    try:
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    prefix = "OFFER-{}-{}-".format(fi, ti)
    out, todo = [], []
    for d in gap_dates:
        ent = cache.get(prefix + d)
        if ent and now - float(ent.get("ts", 0)) < FILL_CACHE_TTL:
            if ent.get("p") is not None:
                out.append(FlightDeal(
                    date=d, bare_price=ent["p"],
                    flight_no=ent.get("fn", ""),
                    dep_time=ent.get("dep", ""), arr_time=ent.get("arr", ""),
                    duration_text=ent.get("dur", ""),
                    time_src="amadeus" if ent.get("dep") else "",
                    dep_src="amadeus" if ent.get("dep") else "",
                    arr_src="amadeus" if ent.get("arr") else "",
                    stop_kind="transfer" if ent.get("stop") else "",
                    stop_city=ent.get("stop", ""),
                source="amadeus-fill"))
        else:
            todo.append(d)
    pending = len(todo)
    todo = todo[:max_days]
    if todo:
        fresh = fetch_fill_offers(session, net, ama_cfg, cfg.get("tax", {}),
                                  fi, ti, todo, data_dir)
        by_date = {x.date: x for x in fresh}
        for d in todo:
            x = by_date.get(d)
            if x:
                out.append(x)
                cache[prefix + d] = {
                    "ts": now, "p": x.bare_price, "fn": x.flight_no,
                    "dep": x.dep_time, "arr": x.arr_time,
                    "dur": x.duration_text, "stop": x.stop_city}
            else:
                cache[prefix + d] = {"ts": now, "p": None}  # negative 24h
        try:
            os.makedirs(data_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass
    if stats is not None:
        stats["holes"] = len(gap_dates)
        stats["probed"] = len(todo)
        stats["deferred"] = max(0, pending - len(todo))
    return out


def _enrich_flight_times(session, net, route, deals, cfg, ama_cfg,
                         ama_ready, date_from, date_to,
                         rec=None, route_id="", direction="out"):
    """Fill duration estimates (great-circle, labeled) + real dep/arr times
    via Amadeus schedules (best-effort, 24h cached, only when key present)."""
    if not deals:
        return deals

    def _mark_time_src(d, exact):
        # weakest mark wins: one borrowed (cross-dow) segment keeps the
        # airport-board-x badge even if the other segment hit an exact dow
        if d.time_src in ("amadeus", "airport-board-x"):
            return
        d.time_src = "airport-board" if exact else "airport-board-x"

    def _mark_dep_src(d, exact):
        if not d.dep_src or d.dep_src == "airport-board-x":
            d.dep_src = "airport-board" if exact else "airport-board-x"

    def _mark_arr_src(d, exact):
        if not d.arr_src or d.arr_src == "airport-board-x":
            d.arr_src = "airport-board" if exact else "airport-board-x"

    fc, tc = route.get("from_city", ""), route.get("to_city", "")
    fi = (route.get("from_iata") or "").strip().upper() or city_iata(fc)
    ti = (route.get("to_iata") or "").strip().upper() or city_iata(tc)
    # v0.49: return legs fly the physical reverse leg (tc->fc). All
    # city-scoped lookups below must use the LEG's cities or return
    # rows would borrow outbound-side times; route-level cities stay
    # untouched for the duration priors (tc's prior is CITY->HGH, which
    # is exactly the return leg's direction).
    if direction == "ret":
        leg_from, leg_to, leg_fi, leg_ti = tc, fc, ti, fi
    else:
        leg_from, leg_to, leg_fi, leg_ti = fc, tc, fi, ti
    by_no = {}
    if ama_ready and fi and ti and any(d.flight_no for d in deals):
        t0 = time.time()
        try:
            rows = fetch_schedule_times(session, net, ama_cfg, leg_fi, leg_ti,
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
    # v0.18/v0.19: zero-key airport-board fallback (core/sched_board.py).
    # Amadeus rows win; the board only fills what Amadeus could not.
    # board_lookup_x first tries the exact weekday, then borrows the same
    # flight number's time from another weekday (calendar data already
    # proves the flight operates that date) -> airport-board-x badge.
    bdb = load_sched_db(DATA_DIR)
    t0b = time.time()
    n_board = 0
    n_x = 0
    n_prior = 0
    # v0.25: real-leg duration priors from the arrive board (reverse leg
    # CITY->HGH minutes) make outbound arr_est/duration far closer to
    # truth than the great-circle guess. Direct flights only: connecting
    # legs keep the +2.5h layover model.
    priors = build_route_priors(bdb)
    alt_cache = {}  # v0.26: per-date city reference departures (numberless deals)
    for d in deals:
        no = (d.flight_no or "").strip()
        if "/" in no:  # connecting itinerary: estimate with layover
            segs = [s.strip().upper() for s in no.split("/") if s.strip()]
            seg_rows = [by_no.get(s) for s in segs]
            # v0.43: cabin rows already carry exact offer times; never
            # downgrade them to generic schedule times.
            if (segs and seg_rows and seg_rows[0] and seg_rows[0].get("dep")
                    and not d.dep_time):
                d.dep_time = seg_rows[0]["dep"]
                d.time_src = "amadeus"
                d.dep_src = "amadeus"
                # v0.33: first-leg arrival is the layover-city landing
                if seg_rows[0].get("arr") and not d.stop_kind:
                    d.stop_kind = "transfer"
                    d.stop_arr = seg_rows[0]["arr"]
            if (segs and seg_rows and seg_rows[-1]
                    and seg_rows[-1].get("arr") and not d.arr_time):
                d.arr_time = seg_rows[-1]["arr"]
                d.time_src = "amadeus"
                d.arr_src = "amadeus"
            if segs:
                hit = board_lookup_x(bdb, segs[0], d.date, leg_from, "")
                if hit and hit[0].get("dep"):
                    ent, exact = hit
                    if not d.dep_time:
                        d.dep_time = ent["dep"]
                        _mark_time_src(d, exact)  # weakest mark wins across segs
                        _mark_dep_src(d, exact)
                        n_board += 1
                        if not exact:
                            n_x += 1
                    # v0.33: transfer info regardless of which source gave
                    # the dep -- the board row deliberately overrides an
                    # amadeus-only stop_arr: same flight, but it also
                    # carries the layover city name (board wins on city)
                    if ent.get("arr") and ent.get("to"):
                        d.stop_kind = "transfer"
                        d.stop_city = ent["to"]
                        d.stop_arr = ent["arr"]
            if not d.arr_time and segs:
                hit = board_lookup_x(bdb, segs[-1], d.date, "", leg_to)
                if hit and hit[0].get("arr"):
                    ent, exact = hit
                    d.arr_time = ent["arr"]
                    _mark_time_src(d, exact)
                    _mark_arr_src(d, exact)
                    n_board += 1
                    if not exact:
                        n_x += 1
            if not d.duration_text:
                d.duration_text = estimate_duration_text(leg_fi, leg_ti,
                                                         connecting=True)
            if not d.dep_time:
                # v0.48: both segments unboarded (e.g. SC2114/SC2135):
                # fall back to the day's same-route reference departures
                # instead of rendering "--:--" for a priced deal.
                if d.date not in alt_cache:
                    alt_cache[d.date] = (
                        city_return_dep_times(bdb, leg_from, d.date)
                        if direction == "ret"
                        else city_dep_times(bdb, leg_to, d.date))
                d.alt_times = alt_cache[d.date]
                best = promote_alt_time(d.alt_times)
                if best:
                    d.dep_time = best["dep"]
                    d.time_src = "alt-ref"
                    d.dep_src = "alt-ref"
            if not d.arr_time and d.dep_time:
                d.arr_est = estimate_arrival_time(d.dep_time, leg_fi, leg_ti,
                                                  connecting=True)
            continue
        row = by_no.get(no.upper())
        if row:
            # v0.43: offer-exact times (cabin rows) win over schedules
            if not d.dep_time:
                d.dep_time = row.get("dep") or ""
            if not d.arr_time:
                d.arr_time = row.get("arr") or ""
            if not d.duration_text:
                d.duration_text = row.get("dur") or ""
            if d.dep_time or d.arr_time:
                d.time_src = "amadeus"
                d.dep_src = "amadeus" if d.dep_time else d.dep_src
                d.arr_src = "amadeus" if d.arr_time else d.arr_src
        if no and not (d.dep_time and d.arr_time):
            hit = board_lookup_x(bdb, no, d.date, leg_from, leg_to)
            if hit:
                ent, exact = hit
                got = False
                if not d.dep_time and ent.get("dep"):
                    d.dep_time = ent["dep"]
                    got = True
                    _mark_dep_src(d, exact)
                if not d.arr_time and ent.get("arr"):
                    d.arr_time = ent["arr"]
                    got = True
                    _mark_arr_src(d, exact)
                if got:
                    n_board += 1
                    _mark_time_src(d, exact)
                    if not exact:
                        n_x += 1
                # v0.33: through-flight stop info (dep-only rows store the
                # stop city + stop arrival from nextschtime). Hop-off rows
                # (via city == this deal's destination) are suppressed:
                # the traveller lands there, "still flying on" copy lies.
                if ent.get("via") and not d.stop_kind and ent["via"] != tc:
                    d.stop_kind = "via"
                    d.stop_city = ent["via"]
                    d.stop_arr = ent.get("via_arr") or ""
        if not (d.flight_no or "").strip() and not d.dep_time:
            # intl calendar deals carry price+date only: give them the
            # board's known same-leg departures for that dow as reference
            # (outbound: HGH->city leave board; return: city->HGH arrive
            # board preschtime, v0.49)
            if d.date not in alt_cache:
                alt_cache[d.date] = (
                    city_return_dep_times(bdb, leg_from, d.date)
                    if direction == "ret"
                    else city_dep_times(bdb, leg_to, d.date))
            d.alt_times = alt_cache[d.date]
            # v0.48: lift the best reference departure onto dep_time so
            # the calendar chip + day detail show a real time (badged).
            best = promote_alt_time(d.alt_times)
            if best:
                d.dep_time = best["dep"]
                d.time_src = "alt-ref"
                d.dep_src = "alt-ref"
        prior_min = prior_minutes_for(priors, tc)
        if not d.duration_text:
            d.duration_text = estimate_duration_text(fi, ti,
                                                    prior_minutes=prior_min)
        if not d.arr_time and d.dep_time:
            d.arr_est = estimate_arrival_time(d.dep_time, fi, ti,
                                             prior_minutes=prior_min)
            if prior_min:
                n_prior += 1
    if rec and (n_board or not ama_ready):
        action = "board time fallback"
        if n_x:
            action += " (cross-dow x%d)" % n_x  # keep error field for errors
        rec.step("hgh-board-times", route_id, action, "ok",
                 (time.time() - t0b) * 1000, count=n_board)
    if rec and n_prior:
        rec.step("hgh-board-times", route_id,
                 "route duration prior (est)", "ok",
                 (time.time() - t0b) * 1000, count=n_prior)
    return deals


def _cabin_absorb(cw, leg, hid, biz_rows, cfg, state, log, push_enabled):
    """v0.66: shared business-cabin collector + alert core.

    Route-scan legs (direct/mirror) and standalone patrol legs both
    land here: business-tagged offers join the ring history, then
    record-low / threshold pushes fire under one cooldown. The caller
    owns the state dict; only cabin_history.json is written here."""
    biz = [d for d in (biz_rows or [])
           if (d.cabin or "") == "business"
           and d.source not in NON_REAL_SOURCES]
    ch = cabin_history_load(DATA_DIR)
    tax_cfg = cfg.get("tax", {})
    new_records = []
    for d in biz:
        ob = cabin_record_low(
            ch, hid, leg["from_city"], leg["to_city"], "business",
            d.date, total_price(d.bare_price, tax_cfg))
        if ob.get("record"):
            new_records.append(ob)
    if biz:
        cabin_atomic_write(
            os.path.join(DATA_DIR, "cabin_history.json"), ch)
    hits = cabin_evaluate_alert(ch, cw)
    st = state.setdefault("_cabin", {})
    prev = st.get("last_alert_ts")
    # v0.52: a fresh all-time low alerts even above the threshold;
    # alerted_low[hid] makes each successive record alert exactly once
    # (same price never twice).
    rec_hit = None
    if cw.get("alert_record_low", True) and new_records:
        rec_hit = cabin_record_candidate(
            new_records, st.setdefault("alerted_low", {}).get(hid))
    if ((rec_hit or hits) and push_enabled
            and cabin_cooldown_ok(prev, cw)):
        if rec_hit is not None:
            under = (" · 已低于阈值 ¥{t}".format(
                t=int(cw.get("threshold_total") or 0))
                if rec_hit["price"]
                <= (cw.get("threshold_total") or 0) else "")
            push_all(cfg, log,
                     "公务舱历史新低 {fc}到{tc}".format(
                         fc=leg["from_city"], tc=leg["to_city"]),
                     "{d} 公务舱 ¥{p} 历史新低(前低 ¥{q}){x}".format(
                         d=rec_hit["date"], p=int(rec_hit["price"]),
                         q=int(rec_hit.get("record_prev")
                               or rec_hit["price"]), x=under),
                     route_id=hid, kind="cabin-record")
            st.setdefault("alerted_low", {})[hid] = rec_hit["price"]
            st["last_hit"] = {
                "route_id": hid,
                "from_city": leg["from_city"],
                "to_city": leg["to_city"],
                "date": rec_hit["date"],
                "price": rec_hit["price"],
                "kind": "record"}
        else:
            h = hits[0]
            push_all(cfg, log,
                     "公务舱低价 {fn}{fc}到{tc}".format(
                         fn="", fc=h["from_city"], tc=h["to_city"]),
                     "{d} 公务舱 ¥{p} (阈值 ¥{t})".format(
                         d=h["date"], p=int(h["price"]),
                         t=int(cw.get("threshold_total") or 0)),
                     route_id=h["route_id"], kind="cabin")
            st["last_hit"] = h
        st["last_alert_ts"] = dt.datetime.now().isoformat()
    return len(biz)


def cabin_patrol_once(cfg, state, log, push_enabled=True, session=None):
    """v0.66: standalone business-cabin patrol on its own cadence.

    watch_from_cities x to_cities legs no configured route feeds get
    fetched directly - a departure city joins the business watch
    without adding a reverse route. Route-covered legs stay with the
    scan (no double fetch). Status lands in state['_cabin_patrol']
    for /api/cabin; the caller persists state."""
    cw = cabin_cfg_load(cfg)
    legs = cabin_patrol_legs(cw, cfg.get("routes") or [])
    info = {
        "last_run": dt.datetime.now().isoformat(timespec="seconds"),
        "interval_minutes": int(cw.get("refresh_minutes") or 30),
        "legs": legs, "offers": 0, "legs_ok": 0,
    }
    ama_cfg = ((cfg.get("sources") or {}).get("amadeus")) or {}
    ready = bool((ama_cfg.get("client_id") or "").strip()
                 and (ama_cfg.get("client_secret") or "").strip())
    if not cw.get("enabled") or not legs:
        info["last_status"] = (
            "skip: 无独立巡检腿 (出发城市未配置或均已由监控路线覆盖)")
    elif not ready:
        info["last_status"] = "skip: Amadeus 密钥未配置"
    else:
        session = session or make_session(cfg)
        today = dt.date.today()
        date_from = (today + dt.timedelta(days=1)).isoformat()
        date_to = (today + dt.timedelta(days=60)).isoformat()
        errs = 0
        for leg in legs:
            hid = "patrol-{fc}-{tc}".format(
                fc=leg["from_city"], tc=leg["to_city"])
            try:
                fi = city_iata(leg["from_city"])
                ti = city_iata(leg["to_city"])
                if not (fi and ti):
                    errs += 1
                    log.warning("cabin patrol iata unknown [{}->{}]".format(
                        leg["from_city"], leg["to_city"]))
                    continue
                biz = fetch_cabin_offers(
                    session, cfg.get("network", {}), ama_cfg,
                    cfg.get("tax", {}), fi, ti, date_from, date_to,
                    cabin=(cw.get("cabins") or ["business"])[0],
                    data_dir=DATA_DIR)
                info["offers"] += _cabin_absorb(
                    cw, leg, hid, biz, cfg, state, log, push_enabled)
                info["legs_ok"] += 1
            except Exception as e:
                errs += 1
                log.warning("cabin patrol failed [{}->{}]: {}".format(
                    leg["from_city"], leg["to_city"], e))
        info["last_status"] = (
            "ok" if not errs and info["legs_ok"]
            else ("partial" if info["legs_ok"] else "error: 采集全部失败"))
    state["_cabin_patrol"] = info
    return info


def run_once(cfg, log, push_enabled=True, verbose=False, trigger="cli"):
    """One full cycle. Returns snapshot dict (also written to data/snapshot.json)."""
    # v0.75: daily auto backup - deploy boxes kept losing the data dir on
    # upgrades; first cycle of each day snapshots before touching anything.
    try:
        from core.auto_backup import maybe_daily_backup
        maybe_daily_backup(os.path.dirname(os.path.abspath(DATA_DIR)), DATA_DIR)
    except Exception:
        pass
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
    # v0.76: point-fill cache - real-browser captured prices replay
    # over reference-only rows on every cycle (zero network).
    point_cache = load_point_cache(DATA_DIR)

    # v0.66: standalone cabin patrol rides every full cycle (manual
    # refresh included); --loop additionally fires it between scans
    # when its own refresh_minutes cadence is shorter.
    try:
        cabin_patrol_once(cfg, state, log, push_enabled, session=session)
    except Exception as e:
        log.warning("cabin patrol cycle failed: {}".format(e))

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

        deals, return_deals, mirror_cabin = [], [], []
        if not use_leg_flight:
            route_snap["flight_source_status"] = "disabled"
            rec.step(flight_key, route_snap["id"], "fetch calendar", "disabled", 0)
            log.info("[{}] flight source disabled, skip".format(route_snap["id"]))
        else:
            t0 = time.time()
            try:
                deals = _fetch_route_flights(session, net, route, date_from,
                                             date_to, cfg, ama_cfg, ama_ready, "out",
                                             rec, route_snap["id"],
                                             cabin_out=mirror_cabin)
                deals = _enrich_flight_times(session, net, route, deals, cfg,
                                             ama_cfg, ama_ready, date_from, date_to,
                                             rec, route_snap["id"])
                deals = _fill_reference_deals(
                    deals, date_from, date_to,
                    route.get("from_city", ""), route.get("to_city", ""))
                deals, npt = merge_point_fill(
                    deals, point_cache, route_snap["id"])
                if npt and rec:
                    rec.step("point-fill", route_snap["id"],
                             "point cache replay", "ok", 0, count=npt)
                deals = _attach_alt_times(
                    deals, route.get("to_city", ""), load_sched_db(DATA_DIR))
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
                        ama_ready, date_from, date_to, rec, route_snap["id"],
                        direction="ret")
                    return_deals = _fill_reference_deals(
                        return_deals, date_from, date_to,
                        route.get("to_city", ""), route.get("from_city", ""))
                    return_deals, nptr = merge_point_fill(
                        return_deals, point_cache, route_snap["id"])
                    if nptr and rec:
                        rec.step("point-fill", route_snap["id"],
                                 "point cache replay (ret)", "ok", 0,
                                 count=nptr)
                    # v0.49: return legs get reference departures from the
                    # arrive board's preschtime rows (CITY->HGH) - the same
                    # zero-key db, zero extra requests
                    return_deals = _attach_alt_times(
                        return_deals, route.get("from_city", ""),
                        load_sched_db(DATA_DIR),
                        from_city=route.get("to_city", ""))
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
        # v0.42: business-cabin low-fare collection + threshold alert.
        # v0.50: mirror legs record under "<id>-rev" with the watch
        # leg's own cities. v0.66: the collector/alert core moved to
        # _cabin_absorb so route legs and standalone patrol legs share
        # one history-key scheme, cooldown and push semantics.
        cw = cabin_cfg_load(cfg)
        leg = cabin_watch_leg(route, cw)
        if leg:
            hid = (route_snap["id"] if leg["mode"] == "direct"
                   else route_snap["id"] + "-rev")
            try:
                _cabin_absorb(cw, leg, hid,
                              deals if leg["mode"] == "direct"
                              else mirror_cabin,
                              cfg, state, log, push_enabled)
            except Exception as e:
                log.warning("cabin monitor failed [{}]: {}".format(
                    route_snap["id"], e))
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
        route_snap["time_coverage"] = time_coverage(deals)
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
                     url=to_alert[0][1].url, route_id=route.get("id"),
                     kind="threshold")
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
                                 push_text, should_push, attach_global_best)
        hist_path = os.path.join(DATA_DIR, "history.json")
        append_history(snapshot, hist_path)
        # v0.55: day-over-day window-min drop watch. A sharp drop (both
        # -drop_pct% and -drop_abs yuan) pushes even while still above
        # the threshold - the threshold line alone stays silent through
        # e.g. 600->400 slides. Deduped per route+day so re-runs never
        # re-alert; state re-saved here because it was persisted before
        # the history block ran.
        try:
            from core.history import day_drops, load_history
            al = cfg.get("alert") or {}
            drops = day_drops(load_history(hist_path),
                              pct=float(al.get("drop_pct") or 15.0),
                              abs_yuan=float(al.get("drop_abs") or 50.0))
            st_drop = state.setdefault("_drop", {})
            fired = False
            for d0 in drops:
                if not d0["sharp"]:
                    continue
                key = d0["route_id"] + "@" + d0["date"]
                if st_drop.get(key):
                    continue
                if push_enabled:
                    push_all(cfg, log,
                             "骤降提醒 {fc}到{tc}".format(
                                 fc=d0["from_city"], tc=d0["to_city"]),
                             "窗口最低 ¥{t} 较昨日 {p}% (¥{d})".format(
                                 t=int(d0["today"]), p=d0["pct"],
                                 d=int(d0["delta"])),
                             route_id=d0["route_id"], kind="drop")
                st_drop[key] = True
                fired = True
            if fired:
                save_state(os.path.join(DATA_DIR, "state.json"), state)
        except Exception:
            log.warning("drop watch failed", exc_info=True)
        wk_path = os.path.join(DATA_DIR, "weekly_push.json")
        if push_enabled and should_push(cfg, wk_path):
            if not has_channel(cfg):
                log.warning("weekly push skipped: no push channel configured "
                            "(timer not consumed)")
            else:
                report = build_weekly(hist_path)
                try:  # v0.65: same global-best merge as the manual push
                    with open(os.path.join(DATA_DIR, "snapshot.json"),
                              encoding="utf-8") as f:
                        attach_global_best(report, json.load(f))
                except Exception:
                    log.debug("global best merge skipped", exc_info=True)
                if report.get("ok"):
                    results = push_all(cfg, log, "📈 FareAlert 价格周报",
                                       push_text(report), url="", kind="weekly")
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
                else:
                    log.debug("weekly report skipped: " + report.get("error", "no history"))
    except Exception:
        log.exception("weekly history/report failed")
    return snapshot


def _write_heartbeat(ok=True):
    """v0.34: worker liveness file, surfaced by /api/health.

    Written after every loop cycle (and after a manual one-shot run) so
    the dashboard can tell "scheduler alive" from "stale deployment".
    """
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "worker_heartbeat.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"ts": time.time(), "pid": os.getpid(),
                       "ok": bool(ok),
                       "code_ver": CODE_VERSION}, f)
    except Exception:
        pass  # heartbeat is best-effort observability, never fatal


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
        push_all(cfg, log, "✈️FareAlert 测试推送", "配置成功!这是测试消息。",
                 url="", kind="test")
        return
    if args.query:
        run_once(cfg, log, push_enabled=False, verbose=True)
        return
    if args.loop:
        interval = int(cfg.get("schedule", {}).get("interval_minutes", 45)) * 60
        jitter = int(cfg.get("schedule", {}).get("jitter_minutes", 10)) * 60
        # v0.66: the cabin patrol keeps its own clock - when its
        # refresh_minutes is shorter than the scan interval it fires
        # between scans (sleep sliced <=60s, no extra thread so state
        # writes stay single-threaded).
        patrol_gap = max(5, int((cfg.get("cabin_watch") or {})
                                .get("refresh_minutes", 30))) * 60
        while True:
            next_patrol = time.time() + patrol_gap
            try:
                run_once(cfg, log)
                _write_heartbeat(True)
            except Exception as e:
                log.error("cycle error: " + str(e))
                _write_heartbeat(False)
            deadline = time.time() + interval + random.randint(0, jitter)
            while time.time() < deadline:
                wake = min(next_patrol, deadline)
                if wake > time.time():
                    time.sleep(min(wake - time.time(), 60.0))
                if time.time() >= deadline:
                    break
                if time.time() >= next_patrol:
                    try:
                        st = load_state(
                            os.path.join(DATA_DIR, "state.json"))
                        cabin_patrol_once(cfg, st, log)
                        save_state(
                            os.path.join(DATA_DIR, "state.json"), st)
                    except Exception:
                        log.exception("cabin patrol cycle failed")
                    next_patrol = time.time() + patrol_gap
        return
    run_once(cfg, log)
    _write_heartbeat(True)


if __name__ == "__main__":
    main()
