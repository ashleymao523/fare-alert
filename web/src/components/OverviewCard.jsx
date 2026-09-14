const fmt = (n) => (typeof n === "number" ? "¥" + Math.round(n) : "-");

// v0.63: mini trend of the whole watch window, straight into the row -
// the board answers "how did it move" without clicking into the route.
// Reuses the spark-line/spark-min classes already shipped for the
// cabin card, so the two line up visually.
function OvSpark({ pts }) {
  if (!pts || pts.length < 2) return null;
  const min = Math.min(...pts), max = Math.max(...pts);
  const W = 84, H = 22, PAD = 2;
  const x = (i) => PAD + (i * (W - 2 * PAD)) / (pts.length - 1);
  const y = (v) => (max === min ? H / 2
    : PAD + ((max - v) / (max - min)) * (H - 2 * PAD));
  const d = pts.map((v, i) => (i ? "L" : "M") + x(i).toFixed(1)
    + " " + y(v).toFixed(1)).join(" ");
  const minI = pts.indexOf(min);
  return (
    <svg viewBox={"0 0 " + W + " " + H} width={W} height={H}
      class="ov-spark" aria-hidden="true">
      <path class="spark-line" d={d} />
      <circle cx={x(minI)} cy={y(min)} r="2.6" class="spark-min" />
    </svg>
  );
}

// v0.61: one-glance board across ALL configured routes, sorted by how
// close each window-lowest sits to its own threshold (best value
// first). Clicking a row switches the dashboard to that route - it
// replaces nothing, it aggregates what previously required tabbing
// through every route chip one by one.
export default function OverviewCard({ routes, drops, currentId, onPick }) {
  const rows = (routes || []).map((r) => {
    const th = Number(r.threshold_total) || 0;
    const priced = (r.deals || [])
      .filter((d) => typeof d.total_price === "number");
    let best = null;
    priced.forEach((d) => {
      if (!best || d.total_price < best.total_price) best = d;
    });
    const cheapest = typeof r.cheapest_total === "number"
      ? r.cheapest_total : (best ? best.total_price : null);
    const ratio = (cheapest != null && th > 0) ? cheapest / th : null;
    return {
      r, th, cheapest, best, ratio,
      drop: (drops || []).find((d) => d.route_id === r.id) || null,
    };
  });
  rows.sort((a, b) => {
    if (a.ratio == null) return 1;
    if (b.ratio == null) return -1;
    return a.ratio - b.ratio;
  });
  if (rows.length < 2) return null;
  // v0.64: rows are ratio-sorted, so the head IS the global best buy
  // across every watched route - surface it as a hero row so "which
  // one should I actually book" has one answer, times included.
  const bestRow = rows[0];
  const daysToGo = (() => {
    if (!bestRow.best || !bestRow.best.date) return null;
    const t = new Date(bestRow.best.date + "T00:00:00");
    if (isNaN(t)) return null;
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return Math.round((t - now) / 86400000);
  })();
  return (
    <div class="card">
      <div class="card-head">
        <h3>🧭 路线总览</h3>
        <span class="sub">按接近心理价位排序 · 点击行直达路线</span>
      </div>
      <div class="ov-list">
        {bestRow.ratio != null && bestRow.best ? (
          <button type="button" class="ov-best"
            onClick={() => onPick(bestRow.r.id, bestRow.best.date)}>
            <span class="ov-best-tag">🏆 全局最优</span>
            <span class="d-route">
              {bestRow.r.from_city}
              {bestRow.r.trip_type === "roundtrip" ? " ⇄ " : " → "}
              {bestRow.r.to_city}
            </span>
            <span class="num">
              {fmt(bestRow.cheapest)}
              {" (" + String(bestRow.best.date).slice(5) + ")"}
            </span>
            {bestRow.best.dep_time || bestRow.best.arr_time ? (
              <span class="ov-times">
                {(bestRow.best.dep_time || "--:--")
                  + "-" + (bestRow.best.arr_time || "")}
              </span>
            ) : null}
            {daysToGo != null && daysToGo >= 0 ? (
              <span class="ov-times">{daysToGo + " 天后出发"}</span>
            ) : null}
            {bestRow.cheapest <= bestRow.th ? (
              <span class="chip2 ok">
                已破线 {fmt(bestRow.th - bestRow.cheapest)} · 省
                {Math.round((bestRow.th - bestRow.cheapest)
                  / bestRow.th * 100)}%
              </span>
            ) : (
              <span class="chip2 plan">
                差 {fmt(bestRow.cheapest - bestRow.th)}
              </span>
            )}
            <span class="ov-arrow">→</span>
          </button>
        ) : null}
        {rows.map(({ r, th, cheapest, best, ratio, drop }) => {
          const pts = (r.deals || [])
            .filter((d) => typeof d.total_price === "number")
            .map((d) => d.total_price);
          const under = cheapest != null && th > 0 && cheapest <= th;
          const gap = (cheapest != null && th > 0)
            ? Math.round(cheapest - th) : null;
          const srcBad = String(r.flight_source_status || "")
            .startsWith("error");
          return (
            <button type="button" key={r.id}
              class={"ov-row" + (r.id === currentId ? " current" : "")}
              onClick={() => onPick(r.id)}>
              <span class="d-route">
                {r.from_city}
                {r.trip_type === "roundtrip" ? " ⇄ " : " → "}
                {r.to_city}
              </span>
              <OvSpark pts={pts} />
              <span class="num">
                {fmt(cheapest)}
                {best && best.date
                  ? " (" + String(best.date).slice(5) + ")" : ""}
              </span>
              {best && (best.dep_time || best.arr_time) ? (
                <span class="ov-times"
                  title={"起飞 " + (best.dep_time || "?") + " · 落地 "
                    + (best.arr_time || "?")}>
                  {(best.dep_time || "--:--")
                    + "-" + (best.arr_time || "")}
                </span>
              ) : null}
              {under ? (
                <span class="chip2 ok">已破线 {(r.days_below || 0) + " 天"}</span>
              ) : (
                <span class="chip2 plan">
                  {gap != null
                    ? "差 " + fmt(gap)
                      + " (+" + Math.round((ratio - 1) * 100) + "%)"
                    : "暂无报价"}
                </span>
              )}
              {drop && drop.delta < 0 ? (
                <span class="d-delta down">
                  {"▼" + Math.abs(Math.round(drop.pct)) + "%"}
                </span>
              ) : drop && drop.delta > 0 ? (
                <span class="d-delta up">
                  {"▲" + Math.round(drop.pct) + "%"}
                </span>
              ) : null}
              {srcBad ? (
                <span class="chip2 plan" title={r.flight_source_status}>
                  源异常
                </span>
              ) : null}
              <span class="ov-arrow">→</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
