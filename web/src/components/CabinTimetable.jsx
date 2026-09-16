
const fmt = (n) => (typeof n === "number" ? "¥" + Math.round(n) : "—");

// v1.13: server-side spark projection - per-date MIN, date-asc, 30 pts
// (fno-less legacy rows count too: they carry a real price).
function SparkPts({ pts }) {
  const p = pts || [];
  if (p.length < 2) {
    return p.length === 1
      ? <span class="muted cab-sp-lab">仅 1 个观测日</span> : null;
  }
  const lo = Math.min(...p.map((x) => x.p));
  const hi = Math.max(...p.map((x) => x.p));
  const W = 120, H = 28, PAD = 4;
  const span = (hi - lo) || 1;
  const x = (i) => PAD + (i * (W - 2 * PAD)) / (p.length - 1);
  const y = (v) => H - PAD - ((v - lo) / span) * (H - 2 * PAD);
  const d = p.map((q, i) => (i ? "L" : "M") + x(i).toFixed(1)
    + " " + y(q.p).toFixed(1)).join(" ");
  const minI = p.findIndex((q) => q.p === lo);
  return (
    <span class="cab-sp" title={"每点=当日最低公务舱含税总价 · 最低 "
      + fmt(lo) + " 于 " + p[minI].d}>
      <svg viewBox={"0 0 " + W + " " + H} width={W} height={H}
        class="cab-sp-svg" aria-hidden="true">
        <path class="cab-sp-line" d={d} />
        <circle cx={x(minI)} cy={y(lo)} r="3" class="cab-sp-dot" />
      </svg>
      <span class="cab-sp-lab">近{p.length}日 {fmt(lo)}–{fmt(hi)}</span>
    </span>
  );
}

export default function CabinTimetable({ timetable }) {
  const groups = timetable || [];
  if (!groups.length) return null;
  return (
    <div class="cab-tt-wrap">
      <div class="cabin-meta">✈️ 逐班公务舱报价 · 采集即真实时刻 · 点击行直达 Booking</div>
      {groups.map((g) => (
        <div class="cab-tt-leg" key={g.route_id}>
          <div class="cab-tt-head">
            <span class="cab-tt-name">{g.from_city} → {g.to_city}</span>
            {g.total ? (
              <span class={"cab-tt-cov" + (g.timed >= g.total ? " full" : "")}
                title={g.timed >= g.total
                  ? "全部班次已带精确起降时刻"
                  : "时刻覆盖 " + g.timed + "/" + g.total
                    + " · 巡检按时刻缺口优先回查"}>
                时刻 {g.timed}/{g.total}
              </span>
            ) : null}
            <SparkPts pts={g.spark} />
          </div>
          <div class="tbl-scroll">
            <table class="tbl cab-tt-table">
              <thead>
                <tr><th>日期</th><th>航班</th><th>起降</th><th>含税总价</th></tr>
              </thead>
              <tbody>
                {(g.rows || []).map((row) => (
                  <tr key={g.route_id + row.date + row.fno + row.price}
                    class={row.url ? "cab-tt-row link" : "cab-tt-row"}
                    title={row.url ? "直达 Booking 公务舱搜索页" : ""}
                    onClick={() => row.url
                      && window.open(row.url, "_blank", "noopener")}>
                    <td>{String(row.date).slice(5)}</td>
                    <td class="num">{row.fno || "—"}</td>
                    <td>{row.dep || row.arr
                      ? (row.dep || "?") + "–" + (row.arr || "?")
                      : "时刻待采"}</td>
                    <td class="price">{fmt(row.price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
