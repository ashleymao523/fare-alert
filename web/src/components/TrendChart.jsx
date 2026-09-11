import { useState } from "preact/hooks";
import { fmtMoney, fmtMD, weekday, dayList } from "../lib/data.js";

const W = 640;
const H = 240;
const PL = 48;
const PR = 64;
const PT = 16;
const PB = 28;

// Catmull-Rom -> cubic bezier: 平滑但不越过数据点
function smoothPath(pp) {
  if (pp.length < 3) {
    return pp.map((q, k) => (k ? "L" : "M") + q.x.toFixed(1) + "," + q.y.toFixed(1)).join(" ");
  }
  let d = "M" + pp[0].x.toFixed(1) + "," + pp[0].y.toFixed(1);
  for (let i = 0; i < pp.length - 1; i++) {
    const p0 = pp[Math.max(0, i - 1)], p1 = pp[i], p2 = pp[i + 1], p3 = pp[Math.min(pp.length - 1, i + 2)];
    d += " C" + (p1.x + (p2.x - p0.x) / 6).toFixed(1) + "," + (p1.y + (p2.y - p0.y) / 6).toFixed(1) +
      " " + (p2.x - (p3.x - p1.x) / 6).toFixed(1) + "," + (p2.y - (p3.y - p1.y) / 6).toFixed(1) +
      " " + p2.x.toFixed(1) + "," + p2.y.toFixed(1);
  }
  return d;
}

const isWknd = (ds) => {
  const w = new Date(ds + "T00:00:00").getDay();
  return w === 0 || w === 6;
};

export default function TrendChart({ route, dealsKey, title, hint }) {
  const [hover, setHover] = useState(null);
  const days = dayList(route);
  const isRTMain = dealsKey === "deals" &&
    !!(route.trip_type === "roundtrip" && route.combined_by_date);
  const map = {};
  (route[dealsKey] || []).forEach((d) => {
    const t = isRTMain && (route.combined_by_date || {})[d.date]
      ? route.combined_by_date[d.date].total
      : d.total_price;
    if (!map[d.date] || t < map[d.date].t) map[d.date] = { t, d };
  });
  const pts = days.map((ds) => {
    const m = map[ds];
    return { date: ds, t: m ? m.t : null, d: m ? m.d : null };
  });
  const vals = pts.filter((p) => p.t != null).map((p) => p.t);
  vals.push(route.threshold_total);
  const vmin = Math.min.apply(null, vals);
  const vmax = Math.max.apply(null, vals);
  const span = (vmax - vmin) || 1;
  const y0 = vmin - span * 0.06;
  const y1 = vmax + span * 0.06;
  const n = pts.length;
  const step = n > 1 ? (W - PL - PR) / (n - 1) : 0;
  const x = (i) => PL + i * step;
  const y = (v) => PT + (1 - (v - y0) / (y1 - y0)) * (H - PT - PB);
  const th = route.threshold_total;

  // 分段折线(缺价日期断开)
  let line = "";
  let area = "";
  let seg = [];
  const segs = [];
  pts.forEach((p, i) => {
    if (p.t == null) {
      if (seg.length) segs.push(seg);
      seg = [];
      return;
    }
    seg.push({ i, p });
  });
  if (seg.length) segs.push(seg);
  const base = H - PB;
  segs.forEach((s) => {
    const pp = s.map((q) => ({ x: x(q.i), y: y(q.p.t) }));
    const d = smoothPath(pp);
    line += d + " ";
    area += "M" + x(s[0].i).toFixed(1) + "," + base + " " +
      d.replace("M", "L") + " L" + x(s[s.length - 1].i).toFixed(1) + "," + base + " Z ";
  });

  let minPt = null;
  pts.forEach((p) => {
    if (p.t != null && (!minPt || p.t < minPt.t)) minPt = p;
  });
  const hp = hover != null ? pts[hover] : null;
  const gridTs = [0, 0.25, 0.5, 0.75, 1].map((f) => y0 + f * (y1 - y0));
  const xEvery = Math.max(1, Math.ceil(n / 8));
  const dotFill = (p) => {
    if (p.d.source === "nearby-ref") return "var(--faint)";
    if (p.d.source === "interp") return "var(--amber)";
    if (p.t < th) return "var(--green)";
    if (p.d.source && p.d.source.indexOf("amadeus") === 0) return "var(--info)";
    return "var(--accent)";
  };
  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const fx = ((e.clientX - r.left) / r.width) * W;
    let idx = Math.round((fx - PL) / step);
    idx = Math.max(0, Math.min(n - 1, idx));
    setHover(idx);
  };
  return (
    <div class="card">
      <div class="card-head">
        <h3>{title}</h3>
        <span class="sub">{hint}</span>
      </div>
      <div class="trend-box">
        <svg
          class="trend-svg"
          viewBox={"0 0 " + W + " " + H}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id="trendGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" style={{ stopColor: "var(--chart-area-a)" }} />
              <stop offset="100%" style={{ stopColor: "var(--chart-area-b)" }} />
            </linearGradient>
          </defs>
          {days.map((ds, i) => isWknd(ds) ? (
            <rect class="t-wknd" x={x(i) - step / 2} y={PT} width={step} height={H - PT - PB} />
          ) : null)}
          {gridTs.map((gv) => (
            <g>
              <line class="t-grid" x1={PL} x2={W - PR} y1={y(gv)} y2={y(gv)} />
              <text class="trend-axis" x={PL - 6} y={y(gv) + 3} text-anchor="end">{Math.round(gv)}</text>
            </g>
          ))}
          {days.map((ds, i) =>
            i % xEvery === 0 ? (
              <text class="trend-axis" x={x(i)} y={H - 8} text-anchor="middle">{fmtMD(ds)}</text>
            ) : null
          )}
          <line class="t-th" x1={PL} x2={W - PR} y1={y(th)} y2={y(th)} />
          <text class="trend-th-label" x={W - PR + 6} y={y(th) + 3}>心理价位 ¥{Math.round(th)}</text>
          {area ? <path class="t-area" d={area} /> : null}
          {line ? <path class="t-line" d={line} /> : null}
          {minPt && minPt.t != null ? (
            <g>
              <circle cx={x(pts.indexOf(minPt))} cy={y(minPt.t)} r="5" style={{ fill: "var(--card)", stroke: "var(--green)", strokeWidth: 2 }} />
              <circle cx={x(pts.indexOf(minPt))} cy={y(minPt.t)} r="2" style={{ fill: "var(--green)" }} />
              <g class="t-min-tag" transform={"translate(" + x(pts.indexOf(minPt)).toFixed(1) + "," + y(minPt.t).toFixed(1) + ")"}>
                <rect x={-24} y={-34} width={48} height={19} rx={9.5} />
                <text x={0} y={-20.5} text-anchor="middle">¥{Math.round(minPt.t)}</text>
              </g>
            </g>
          ) : null}
          {pts.map((p, i) => {
            if (p.t == null || p === minPt) return null;
            // 只画信息点(低于阈值/参考/插值), 普通点由平滑曲线自身表达
            if (p.t >= th && p.d.source !== "nearby-ref" && p.d.source !== "interp") return null;
            return <circle class="t-dot" cx={x(i)} cy={y(p.t)} r={p.t < th ? 3.2 : 2.6} style={{ fill: dotFill(p) }} />;
          })}
          {hp && hp.t != null ? (
            <g>
              <line class="t-cross" x1={x(hover)} x2={x(hover)} y1={PT} y2={H - PB} />
              <circle cx={x(hover)} cy={y(hp.t)} r="4.5" style={{ fill: "var(--card)", stroke: dotFill(hp), strokeWidth: 2 }} />
            </g>
          ) : null}
        </svg>
        {hp && hp.t != null ? (
          <div class="trend-tip" style={{ left: (x(hover) / W) * 100 + "%", top: (y(hp.t) / H) * 100 + "%" }}>
            <b>{fmtMoney(hp.t)}</b> {hp.date} {weekday(hp.date)}<br />
            {hp.d.flight_no || hp.d.airline || ""}{hp.d.dep_time ? " · " + hp.d.dep_time + "起飞" : ""}
            {hp.d.source === "nearby-ref" ? " · 临近日参考" : ""}
            {hp.d.source === "interp" ? " · 插值估算" : ""}
          </div>
        ) : null}
      </div>
    </div>
  );
}
