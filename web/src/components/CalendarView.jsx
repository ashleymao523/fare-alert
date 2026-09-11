import { fmtMoney, fmtMD, weekday, parseDate, dayList, heatClass } from "../lib/data.js";

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
      {view === "bars"
        ? <Bars route={route} map={map} days={days} selDate={selDate} onSelect={onSelect} />
        : <CalGrid route={route} map={map} days={days} selDate={selDate} onSelect={onSelect} />}
    </div>
  );
}
