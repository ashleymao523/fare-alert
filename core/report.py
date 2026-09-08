# -*- coding: utf-8 -*-
"""Local HTML low-price calendar report + latest.json."""
import datetime as dt
import html
import json
import os

from .alerts import WEEKDAY_CN, tax_amount, total_price
from .flights import airline_name


def _weekday(date_str):
    return WEEKDAY_CN[dt.date.fromisoformat(date_str).weekday()]


def write_report(cfg, route_cfg, deals, train_info, state, out_dir, alert_dates=None):
    tax_cfg = cfg.get("tax", {})
    tax = tax_amount(tax_cfg)
    threshold = route_cfg.get("threshold_total", 500)
    bag = cfg.get("baggage_policy", {})
    alert_dates = alert_dates or set()

    rows = []
    for d in deals:
        total = total_price(d.bare_price, tax_cfg)
        code = d.airline_code
        bag_note = bag.get(code, "以购票页为准")
        below = total < threshold
        rows.append(
            "<tr class='{}'><td>{}</td><td>{}</td><td>{}</td><td>¥{}</td><td><b>¥{}</b></td>"
            "<td>{} {}</td><td>{}</td><td><a href='{}'>买</a></td></tr>".format(
                "low" if below else "",
                d.date, _weekday(d.date),
                "🚨" if d.date in alert_dates else "",
                int(d.bare_price), int(total),
                html.escape(d.flight_no), html.escape(airline_name(code)),
                html.escape(bag_note),
                html.escape(d.url),
            ))

    train_html = []
    if train_info and train_info.get("pairs"):
        train_html.append("<h3>🚄 动车对比(次日参考, 查询于 {})</h3>".format(
            html.escape(str(train_info.get("updated_at", "")))))
        train_html.append("<table><tr><th>车次</th><th>区间</th><th>时刻</th><th>历时</th><th>二等座</th><th>学生票≈</th></tr>")
        all_fares = []
        for pair, items in train_info["pairs"].items():
            if isinstance(items, dict):
                continue
            for it in items:
                all_fares.append((pair, it))
        all_fares.sort(key=lambda x: (x[1].get("second_class") or 9e9))
        for pair, it in all_fares[:20]:
            sc = it.get("second_class")
            train_html.append("<tr><td>{}</td><td>{}→{}</td><td>{}-{} [{}]</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                html.escape(it["train_code"]),
                html.escape(it["from_station"]), html.escape(it["to_station"]),
                html.escape(it["dep_time"]), html.escape(it["arr_time"]),
                html.escape(pair),
                html.escape(it["duration_text"]),
                "¥" + str(int(sc)) if sc else "--",
                "¥" + str(int(sc * 0.75)) if sc else "--",
            ))
        train_html.append("</table><p>学生票=二等座公布价75折;上表按执行价估算偏低,以12306下单页为准。</p>")

    n_below = sum(1 for d in deals if total_price(d.bare_price, tax_cfg) < threshold)
    doc = """<!doctype html><html lang=zh><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{}→{} 低价日历</title><style>
body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;margin:24px;background:#f6f7f9;color:#222}}
h2{{margin:0 0 4px}} .sub{{color:#666;margin-bottom:16px}}
table{{border-collapse:collapse;background:#fff;width:100%;max-width:900px;font-size:14px}}
th,td{{padding:6px 10px;border-bottom:1px solid #eee;text-align:left}}
th{{background:#eef1f4;position:sticky;top:0}}
tr.low td{{background:#e8f8ee}} tr.low td:nth-child(6){{color:#0a7d32;font-weight:700}}
a{{color:#2563eb;text-decoration:none}}
.meta{{color:#888;font-size:12px;margin-top:8px}}
</style></head><body>
<h2>✈️ {}→{} 未来{}天最低票价</h2>
<div class=sub>总价=裸价+机建+燃油(¥{}) | 低于阈值¥{}共 <b>{}</b> 天 | 含免费托运情况见表格,廉航特价票下单前务必确认 | 生成于 {}</div>
<table><tr><th>日期</th><th>周</th><th></th><th>裸价</th><th>总价</th><th>航班</th><th>行李</th><th></th></tr>
{}
</table>
{}
<p class=meta>数据源: 去哪儿价格日历(挂牌价,不含平台券后价) + 12306. 本页仅为个人比价参考。</p>
</body></html>""".format(
        html.escape(route_cfg["from_city"]), html.escape(route_cfg["to_city"]),
        html.escape(route_cfg["from_city"]), html.escape(route_cfg["to_city"]),
        len(deals), int(tax), int(threshold), n_below,
        dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "\n".join(rows), "\n".join(train_html))

    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(doc)
    latest = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "route": route_cfg["id"],
        "threshold_total": threshold,
        "days_below_threshold": n_below,
        "cheapest": [{
            "date": d.date, "bare_price": d.bare_price,
            "total_price": total_price(d.bare_price, tax_cfg),
            "flight_no": d.flight_no,
            "airline": airline_name(d.airline_code),
            "url": d.url,
        } for d in deals[:10]],
    }
    with open(os.path.join(out_dir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=1)
    return html_path
