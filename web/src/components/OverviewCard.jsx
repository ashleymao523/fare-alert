const fmt = (n) => (typeof n === "number" ? "¥" + Math.round(n) : "-");

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
  return (
    <div class="card">
      <div class="card-head">
        <h3>🧭 路线总览</h3>
        <span class="sub">按接近心理价位排序 · 点击行直达路线</span>
      </div>
      <div class="ov-list">
        {rows.map(({ r, th, cheapest, best, ratio, drop }) => {
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
              <span class="num">
                {fmt(cheapest)}
                {best && best.date
                  ? " (" + String(best.date).slice(5) + ")" : ""}
              </span>
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
