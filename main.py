# -*- coding: utf-8 -*-
"""FareAlert: monitor lowest flight fares (tax-included) vs student train fares."""
import argparse
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
from core.flights import airline_name, fetch_calendar
from core.intl import fetch_intl_calendar
from core.models import FlightDeal
from core.notify import push_all
from core.report import write_report
from core.state import load_state, save_state
from core.trains import refresh_train_info

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def setup_logging():
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
    }


def _fetch_route_flights(session, net, route, date_from, date_to,
                         cfg, ama_cfg, ama_ready, direction="out"):
    """Fetch one leg's calendar. direction 'out'/'ret' swaps the cities."""
    if direction == "ret":
        fc, tc = route.get("to_city", ""), route.get("from_city", "")
        fi, ti = route.get("to_iata", ""), route.get("from_iata", "")
    else:
        fc, tc = route.get("from_city", ""), route.get("to_city", "")
        fi, ti = route.get("from_iata", ""), route.get("to_iata", "")
    if route.get("intl"):
        if not ama_ready:
            raise RuntimeError("国际线路已启用但Amadeus密钥未配置")
        return fetch_intl_calendar(session, net, ama_cfg, cfg.get("tax", {}),
                                   fi, ti, date_from, date_to, DATA_DIR)
    return fetch_calendar(session, net, fc, tc, date_from, date_to)


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
    snapshot_routes = []
    pending_push = []

    for route in cfg.get("routes", []):
        date_from = (today + dt.timedelta(days=1)).isoformat()
        date_to = (today + dt.timedelta(days=int(route.get("window_days", 60)))).isoformat()
        trip_type = "roundtrip" if route.get("trip_type") == "roundtrip" else "oneway"
        intl = bool(route.get("intl"))
        flight_key = "amadeus-intl" if intl else "qunar-calendar"
        ama_cfg = ((cfg.get("sources") or {}).get("amadeus")) or {}
        ama_ready = bool((ama_cfg.get("client_id") or "").strip()
                         and (ama_cfg.get("client_secret") or "").strip())
        use_leg_flight = use_flight and (not intl or enabled.get("amadeus-intl", True))
        route_snap = {
            "id": route.get("id", "route"),
            "from_city": route.get("from_city", ""),
            "to_city": route.get("to_city", ""),
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
                                             date_to, cfg, ama_cfg, ama_ready, "out")
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
                                                        ama_cfg, ama_ready, "ret")
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

        alert_deals, combined_meta, combined_by_date = deals, None, {}
        if trip_type == "roundtrip" and deals and return_deals:
            tax_cfg = cfg.get("tax", {})
            ret_sorted = sorted(return_deals, key=lambda x: (x.bare_price, x.date))
            alert_deals = []
            for d1 in deals:
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
        elif deals:
            route_snap["cheapest_total"] = total_price(deals[0].bare_price, cfg.get("tax", {}))
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
