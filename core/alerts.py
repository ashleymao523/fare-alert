# -*- coding: utf-8 -*-
"""Threshold evaluation, dedupe rules and message composition."""

from .flights import airline_name

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def total_price(bare, tax_cfg):
    if tax_cfg.get("calendar_price_includes_tax"):
        return bare
    return bare + tax_cfg.get("airport_fee", 0) + tax_cfg.get("fuel_surcharge", 0)


def tax_amount(tax_cfg):
    if tax_cfg.get("calendar_price_includes_tax"):
        return 0
    return tax_cfg.get("airport_fee", 0) + tax_cfg.get("fuel_surcharge", 0)


def evaluate(route_cfg, deals, state, cfg, now_ts, record=True):
    """Return (alert_list, below_list). alert_list = [(total, deal)] to push now."""
    threshold = route_cfg.get("threshold_total", 500)
    alert_cfg = cfg.get("alert", {})
    tax_cfg = cfg.get("tax", {})
    route_state = (state.setdefault("routes", {})
                   .setdefault(route_cfg["id"], {})
                   .setdefault("dates", {}))

    below = []
    for d in deals:
        total = total_price(d.bare_price, tax_cfg)
        if total < threshold:
            below.append((total, d))
    below.sort(key=lambda x: (x[0], x[1].date))

    to_alert = []
    top_n = int(alert_cfg.get("top_n", 5))
    cooldown_s = float(alert_cfg.get("cooldown_hours", 6)) * 3600
    realert_drop = float(alert_cfg.get("realert_drop", 5))
    for total, d in below[:top_n]:
        prev = route_state.get(d.date) or {}
        last_total = prev.get("last_alert_total")
        last_ts = float(prev.get("last_alert_ts", 0))
        first_time = last_total is None
        dropped = (last_total is not None
                   and (last_total - total) >= realert_drop)
        if (first_time or dropped) and (now_ts - last_ts) > cooldown_s:
            to_alert.append((total, d))
            if record:
                min_seen = min(total, prev.get("min_total_seen", total))
                route_state[d.date] = {
                    "last_alert_total": total,
                    "last_alert_ts": now_ts,
                    "min_total_seen": min_seen,
                }
    return to_alert, below


def _fmt_date(date_str):
    import datetime as dt
    d = dt.date.fromisoformat(date_str)
    return d.strftime("%m-%d") + " " + WEEKDAY_CN[d.weekday()]


def _train_lines(train_info):
    if not train_info or not train_info.get("pairs"):
        return ["🚄列车: 暂无数据"]
    items = []
    for pair, its in train_info["pairs"].items():
        if isinstance(its, dict):
            continue
        items.extend(x for x in its if isinstance(x, dict) and x.get("seats"))
    if not items:
        return ["🚄列车: 未查到席位票价"]
    lines = [
        "🚄列车对比(次日参考, 全席位):",
    ]
    ze = [it for it in items if it["seats"].get("二等座")]
    if ze:
        c = min(ze, key=lambda it: it["seats"]["二等座"])
        lines.append("最低二等 {} {} {}→{} 二等¥{} 学生≈¥{}".format(
            c["train_code"], c["pair"].replace("-", "→"),
            c["dep_time"], c["arr_time"],
            int(c["seats"]["二等座"]), int(c["seats"]["二等座"] * 0.75)))
    sleepers = []
    for it in items:
        sl = [(l, p) for l, p in it["seats"].items() if "卧" in l]
        if sl:
            lab, pr = min(sl, key=lambda kv: kv[1])
            sleepers.append((pr, lab, it))
    if sleepers:
        sleepers.sort(key=lambda x: x[0])
        pr, lab, it = sleepers[0]
        yz = it["seats"].get("硬座")
        stu = " 学生≈¥{}".format(int(pr - yz * 0.5)) if yz else ""
        lines.append("最低卧铺 {} {} {}→{} {}¥{}{}".format(
            it["train_code"], it["pair"].replace("-", "→"),
            it["dep_time"], it["arr_time"], lab, int(pr), stu))

    def dur_min(it):
        try:
            h, m = it.get("duration_text", "").split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 10 ** 6

    fastest = min(items, key=dur_min)
    if fastest.get("duration_text"):
        ms, lab = None, None
        if fastest["seats"]:
            lab, ms = min(fastest["seats"].items(), key=lambda kv: kv[1])
        lines.append("最快 {} 历时{} {}¥{}".format(
            fastest["train_code"], fastest["duration_text"],
            lab or "", int(ms) if ms else ""))
    lines.append("(学生票: 动车组二等座公布价75折/硬座5折/硬卧=硬卧-硬座半价,均为估算,以12306下单页为准)")
    return lines


def build_message(route_cfg, to_alert, below, train_info, cfg):
    tax_cfg = cfg.get("tax", {})
    tax = tax_amount(tax_cfg)
    bag = cfg.get("baggage_policy", {})
    threshold = route_cfg.get("threshold_total", 500)

    top_total, top_deal = to_alert[0]
    title = "✈️{}→{} 低于¥{}: ¥{} ({})".format(
        route_cfg["from_city"], route_cfg["to_city"],
        int(threshold), int(top_total), _fmt_date(top_deal.date))

    body = []
    for total, d in to_alert:
        code = d.airline_code
        name = airline_name(code)
        bag_note = bag.get(code, "托运额度以购票页为准")
        warn = "⚠️" if ("不含" in bag_note or "确认" in bag_note) else "🧳"
        body.append("{} {} {} 裸价¥{}+税¥{}=¥{} {}{}".format(
            _fmt_date(d.date), d.flight_no, name,
            int(d.bare_price), int(tax), int(total), warn, bag_note))
    body.append("")
    body.append("60天窗口内共{}天低于¥{}".format(len(below), int(threshold)))
    body.append("")
    body.extend(_train_lines(train_info))
    body.append("")
    body.append("购票: " + top_deal.url)
    return title, "\n".join(body)
