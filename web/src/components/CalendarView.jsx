import { useEffect, useState } from "react";
import { fmtMoney, fmtMD, weekday, parseDate, dayList, heatClass } from "../lib/data.js";
import { fetchTimeCoverage } from "../lib/api.js";

const KIND_LABEL = {
  exact: "当日真实时刻",   // v1.03: 板库/Amadeus/Booking同日行程/精点回填
  borrow: "参考借用时刻",  // v1.03: 跨周借班 + booking-x 同日他航班参考
  alt: "邻近参考时刻",
  noref: "无时刻·待精查",
};

let covCache = null; // module cache: one /api/time-coverage per session

function TimeStrip({ routeId }) {
  const [cov, setCov] = useState(null);
  useEffect(() => {
    let live = true;
    if (covCache) { setCov(covCache); return; }
    fetchTimeCoverage()
      .then((x) => { covCache = x; if (live) setCov(x); })
      .catch(() => {});
    return () => { live = false; };
  }, []);
  if (!cov) return null;
  const mine = (cov.routes || []).find((r) => r.id === routeId);
  if (!mine || !(mine.days || []).length) return null;
  const c = mine.counts || {};
  const heals = (cov.heal || []).map((h) =>
    "周" + "日一二三四五六"[h.dow] + " " + fmtMD(h.on) + " 板库轮询补齐");
  return (
    <div class="tstrip">
      <div class="tstrip-legend">
        <span class="tl"><i class="dot exact" />真实 {c.exact || 0}</span>
        <span class="tl"><i class="dot borrow" />借班 {c.borrow || 0}</span>
        <span class="tl"><i class="dot alt" />参考 {c.alt || 0}</span>
        <span class="tl"><i class="dot noref" />无时刻 {c.noref || 0}</span>
        {heals.length ? <span class="tl heal">⏳ {heals.join(" · ")}</span> : null}
      </div>
      <div class="tstrip-track">
        {(mine.days || []).map((d) => (
          <div
            key={d.date}
            class={"cell " + d.kind}
            title={d.date + " " + weekday(d.date) + " · " + KIND_LABEL[d.kind]
              + (d.dep ? " · " + (d.flight || "") + " " + d.dep
                + (d.arr ? "→" + d.arr : "") : "")
              + (d.promote_on ? " · " + fmtMD(d.promote_on) + " 转精查" : "")}
          />
        ))}
      </div>
    </div>
  );
}

function bestByDate(route) {
  const isRT = !!(route.trip_type === "roundtrip" && route.combined_by_date);
  const map = {};
  (route.deals || []).forEach((d) => {
    const t = isRT && (route.combined_by_date || {})[d.date]
      ? route.combined_by_date[d.date].total
      : d.total_price;
    if (!map[d.date] || t < map[d.date].t) map[d.date] = { t, d };
  });
  return map;
}

function Bars({ route, map, days, selDate, onSelect }) {
  const prices = Object.values(map).map((m) => m.t).filter((p) => p > 0).sort((a, b) => a - b);
  if (!prices.length) return <div class="empty">暂无价格数据</div>;
  const pmin = prices[0];
  const pmax = prices[prices.length - 1];
  return (
    <div>
      <div class="bars-hint">柱越低越便宜 · 绿=低于心理价位 · 斜纹=临近日参考价 · 点击柱看详情</div>
      <div class="bars-wrap">
        {days.map((ds) => {
          const m = map[ds];
          const wd = parseDate(ds).getDay();
          const ratio = m
            ? (pmax > pmin ? 0.25 + 0.75 * (1 - (m.t - pmin) / (pmax - pmin)) : 1)
            : 0;
          const barCls = m
            ? "bar" +
              (m.t < route.threshold_total ? " cheap" : "") +
              (m.d.source === "nearby-ref" ? " ref" : "") +
              (m.d.source === "interp" ? " interp" : "")
            : "";
          const title = m
            ? ds + " " + weekday(ds) + " · " + fmtMoney(m.t) +
              (m.d.source === "nearby-ref"
                ? " (临近日参考" + (m.d.ref_offset ? " · 距" + m.d.ref_offset + "天" : "") + ")"
                : m.d.source === "interp" ? " (两侧真实价插值估算)" : "")
            : ds + " " + weekday(ds) + " · 无数据";
          return (
            <div
              class={"bar-col" + (ds === selDate ? " selected" : "")}
              title={title}
              onClick={() => m && onSelect(ds)}
            >
              {m && (
                <div class="bar-price">
                  {(m.d.source === "nearby-ref" || m.d.source === "interp" ? "≈" : "") + Math.round(m.t)}
                </div>
              )}
              <div class="bar-track">
                {m ? <div class={barCls} style={{ height: Math.round(ratio * 100) + "%" }} /> : null}
              </div>
              <div class={"bar-date" + ((wd === 0 || wd === 6) ? " wk" : "")}>{fmtMD(ds)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CalGrid({ route, map, days, selDate, onSelect }) {
  const lead = days.length ? parseDate(days[0]).getDay() : 0;
  const th = route.threshold_total;
  const cells = [];
  for (let i = 0; i < lead; i++) {
    cells.push(<div class="day empty-cell" />);
  }
  days.forEach((ds) => {
    const m = map[ds];
    const wd = parseDate(ds).getDay();
    if (!m) {
      cells.push(
        <div class="day" title={ds + " " + weekday(ds) + " · 暂无报价"}>
          <div class={"d-date" + ((wd === 0 || wd === 6) ? " wk" : "")}>{fmtMD(ds)}</div>
          <div class="d-price muted">--</div>
        </div>
      );
      return;
    }
    const src = m.d.source;
    const cls = "day has " + heatClass(m.t, th) +
      (src === "nearby-ref" ? " ref" : "") +
      (src === "interp" ? " interp" : "") +
      (ds === selDate ? " selected" : "");
    const chip = m.d.dep_time
      ? m.d.dep_time + "起飞"
      : (m.d.flight_no || ((m.d.alt_times || []).length ? (m.d.alt_times[0].no + " " + m.d.alt_times[0].dep) : ""));
    cells.push(
      <div
        class={cls}
        title={ds + " " + weekday(ds) + " " + fmtMoney(m.t) + (chip ? " · " + chip : "")}
        onClick={() => onSelect(ds)}
      >
        <div class={"d-date" + ((wd === 0 || wd === 6) && src !== "nearby-ref" ? " wk" : "")}>{fmtMD(ds)}</div>
        <div class="d-price">
          {(src === "nearby-ref" || src === "interp" ? "≈" : "") + Math.round(m.t)}
        </div>
        {chip ? <div class="d-flight">{chip}</div> : null}
      </div>
    );
  });
  return (
    <div class="cal-scroll">
      <div class="cal-grid">
        {["日", "一", "二", "三", "四", "五", "六"].map((w) => <div class="cal-dow">周{w}</div>)}
        {cells}
      </div>
    </div>
  );
}

export default function CalendarView({ route, selDate, onSelect, view, onView }) {
  if (!route) return null;
  const days = dayList(route);
  const map = bestByDate(route);
  const isRT = !!(route.trip_type === "roundtrip" && route.combined_by_date);
  return (
    <div class="card">
      <div class="card-head">
        <h3>🗓 60天低价日历</h3>
        <div class="cal-tools">
          <span class="sub">{isRT ? "往返模式 · 显示往返合计价" : "含税总价 · 点击日期看详情"}</span>
          <div class="seg">
            <button class={view === "cal" ? "active" : ""} onClick={() => onView("cal")}>日历</button>
            <button class={view === "bars" ? "active" : ""} onClick={() => onView("bars")}>条形</button>
          </div>
        </div>
      </div>
      <TimeStrip routeId={route.id} />
      {view === "bars"
        ? <Bars route={route} map={map} days={days} selDate={selDate} onSelect={onSelect} />
        : <CalGrid route={route} map={map} days={days} selDate={selDate} onSelect={onSelect} />}
    </div>
  );
}
