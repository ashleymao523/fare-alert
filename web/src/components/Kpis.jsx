import { fmtMoney, fmtMD, weekday, trainSeats, cheapestFlight, trainBest } from "../lib/data.js";

function Kpi({ it }) {
  const Tag = it.url ? "a" : "div";
  const props = it.url
    ? { href: it.url, target: "_blank", rel: "noopener", title: "点击直达购票/查票页" }
    : {};
  const d = it.delta;
  const dchip = (d && typeof d.delta === "number") ? (
    <span class={"d-delta " + (d.delta < 0 ? "down" : "up")}>
      {"较昨日 " + (d.delta < 0 ? "▼" : "▲") + " ¥" + Math.abs(Math.round(d.delta)) + " (" + d.pct + "%)"}
    </span>
  ) : null;
  return (
    <Tag class={"kpi" + (it.cls ? " " + it.cls : "")} {...props}>
      <div class="k-label">{it.label}</div>
      <div class="k-value">{it.value}</div>
      <div class="k-sub">{dchip} {it.sub}</div>
    </Tag>
  );
}

export default function Kpis({ route, drop }) {
  if (!route || !route.deals || !route.deals.length) {
    return (
      <div class="kpis">
        <div class="kpi">
          <div class="k-label">暂无数据</div>
          <div class="k-value">--</div>
          <div class="k-sub">{route ? route.flight_source_status || "-" : "-"}</div>
        </div>
      </div>
    );
  }
  const f = cheapestFlight(route);
  const isRT = !!(route.trip_type === "roundtrip" && route.combined);
  const tr = trainBest(route);
  // v0.55: day-over-day window-min change from the KPI archive; the
  // chip makes "is today cheaper than yesterday" glanceable and a
  // sharp drop has already gone through the push pipeline.
  const dlt = drop && typeof drop.delta === "number" ? drop : null;
  const items = [{
    label: isRT ? "往返合计最低" : "最低机票总价",
    value: fmtMoney(isRT ? route.combined.total : f.total_price),
    sub: (isRT
      ? "去 " + fmtMD(route.combined.out_date) + " · 返 " + fmtMD(route.combined.ret_date) + " · 最优组合(去+返)"
      : f.date + " " + weekday(f.date) + " · " + (f.flight_no || f.airline) +
        (f.source === "amadeus-fill" ? " · Amadeus补" : "")),
    delta: dlt,
    cls: (isRT ? route.combined.total : f.total_price) < route.threshold_total ? "good" : "",
    url: isRT ? (route.combined.url || f.url) : f.url
  }, {
    label: "低于心理价位",
    value: route.days_below + " 天",
    sub: "窗口 " + route.window[0] + " ~ " + route.window[1],
    cls: route.days_below > 0 ? "good" : "warn"
  }];
  const ds = route.deals || [];
  const real = ds.filter((x) => ["nearby-ref", "interp", "booking-ref"]
    .indexOf(x.source) < 0);
  let depN = 0;
  let altN = 0;
  real.forEach((x) => {
    // v0.48: alt-ref promoted times stay in the "参考" bucket so the
    // KPI never counts a different flight's departure as exact.
    // v0.88: booking-x (Booking same-date itinerary pinned onto a
    // real-price row) is the same kind of cross-flight reference.
    if ((x.dep_time || "").trim()
      && x.dep_src !== "alt-ref" && x.dep_src !== "booking-x") depN++;
    else if ((x.dep_time || "").trim() || (x.alt_times || []).length) altN++;
  });
  const refN = ds.length - real.length;
  if (real.length) {
    items.push({
      label: "真实票时刻覆盖",
      value: Math.round(100 * (depN + altN) / real.length) + "%",
      sub: (altN
        ? "精确 " + depN + " 天 · 参考 " + altN + " 天"
        : "班期库每日自动沉淀, 约7天长滑窗")
        + (route.time_coverage && route.time_coverage.promote_on
          ? " · " + fmtMD(route.time_coverage.promote_on) + " 起借班转精查" : "")
        + (refN ? " · 另参考价 " + refN + " 天(无时刻)" : ""),
      cls: ""
    });
  }
  items.push({
    label: isRT ? "心理价位(往返合计)" : "心理价位(含税)",
    value: fmtMoney(route.threshold_total),
    sub: "低于即推送提醒"
  });
  if (tr.second) {
    const ze = trainSeats(tr.second)["二等座"];
    items.push({
      label: "动车二等最低",
      value: fmtMoney(ze),
      sub: tr.second.train_code + " " + tr.second.dep_time + "开 · 历时" + tr.second.duration_text,
      url: tr.second.url
    });
    items.push({
      label: "学生动车 ≈",
      value: fmtMoney(ze * 0.75),
      sub: "二等座公布价75折估算 · 点击直达12306",
      cls: "good",
      url: tr.second.url
    });
  }
  if (tr.sleeper) {
    items.push({
      label: "最低卧铺",
      value: fmtMoney(tr.sleeper.price),
      sub: tr.sleeper.train.train_code + " " + tr.sleeper.label + " · 历时" + tr.sleeper.train.duration_text,
      cls: "good",
      url: tr.sleeper.train.url
    });
  }
  return <div class="kpis">{items.map((it) => <Kpi it={it} />)}</div>;
}
