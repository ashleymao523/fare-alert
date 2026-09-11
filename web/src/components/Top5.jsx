import { fmtMoney, fmtMD, weekday, dealForDate, dayList, isRefDeal } from "../lib/data.js";

export default function Top5({ route }) {
  const deals = (route && route.deals) || [];
  if (!deals.length) return null;
  const th = route.threshold_total;
  const rows = dayList(route)
    .map((ds) => dealForDate(route, ds))
    .filter((d) => d && !isRefDeal(d))
    .sort((a, b) => a.total_price - b.total_price)
    .slice(0, 5);
  return (
    <div class="card">
      <div class="card-head">
        <h3>🏅 最低五日</h3>
        <span class="sub">真实抓取价 · 含税总价 · 点击直达</span>
      </div>
      <div class="tbl-scroll">
        <table class="tbl">
          <thead>
            <tr><th>#</th><th>日期</th><th>总价</th><th>航班</th><th>行李</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((d, i) => (
              <tr class={d.total_price < th ? "cheap-row" : ""}>
                <td>{i + 1}</td>
                <td><b>{fmtMD(d.date)}</b> {weekday(d.date)}</td>
                <td class="num">¥{Math.round(d.total_price)}</td>
                <td>
                  {(d.airline || "—") + " " + (d.flight_no || "")}
                  {d.dep_time ? <div class="muted">{d.dep_time}起飞</div> : null}
                  {d.source === "amadeus-fill" ? <span class="badge amber">Amadeus补</span> : null}
                </td>
                <td>{d.baggage === false ? "无免费托运" : (d.baggage === true ? "含免费托运" : "以舱位为准")}</td>
                <td><a class="btn small" href={d.url || "#"} target="_blank" rel="noopener">直达购票 →</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
