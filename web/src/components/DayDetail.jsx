import { fmtMoney, fmtMD, weekday, trainSeats, trainBest, dealForDate } from "../lib/data.js";

function srcBadge(d) {
  if (d.source === "qunar-intl") return <span class="badge sky">国际特价</span>;
  if (d.source === "amadeus-intl") return <span class="badge sky">Amadeus</span>;
  if (d.source === "amadeus-fill") return <span class="badge amber">Amadeus补</span>;
  if (d.source === "nearby-ref") {
    return <span class="badge gray">{d.ref_offset ? "临近日参考 · 距" + d.ref_offset + "天" : "临近日参考"}</span>;
  }
  if (d.source === "interp") return <span class="badge amber">两侧真实价插值</span>;
  return null;
}

function timeSrcBadge(label, src) {
  if (src === "airport-board") return <span class="badge gray ts-badge">{label}·班期精查</span>;
  if (src === "airport-board-x") {
    return (
      <span class="badge amber ts-badge" title="同一航班号其他班期的时刻, 同航季通常一致, 仅供参考">
        {label}·跨日参考
      </span>
    );
  }
  if (src === "amadeus") return <span class="badge sky ts-badge">{label}·Amadeus</span>;
  return null;
}

export default function DayDetail({ route, date }) {
  if (!route || !date) return null;
  const d = dealForDate(route, date);
  const tr = trainBest(route);
  if (!d) {
    return (
      <div class="card">
        <div class="dd-title">{date} {weekday(date)} · 该日无报价</div>
      </div>
    );
  }
  const below = d.total_price < route.threshold_total;
  const isRT = !!(route.trip_type === "roundtrip" && d.ret_date);
  const hasDep = !!(d.dep_time || "").trim();
  const hasArr = !!(d.arr_time || "").trim();
  const hasEst = !hasArr && !!d.arr_est;
  const depSrc = d.dep_src || (d.dep_time ? d.time_src : "");
  const arrSrc = d.arr_src || (d.arr_time ? d.time_src : "");
  const connecting = (d.flight_no || "").indexOf("/") >= 0;
  const warn = /不含|确认/.test(d.baggage || "") ? " ⚠️" : " 🧳";
  const alts = d.alt_times || [];
  const shownArr = hasArr ? d.arr_time : (hasEst ? d.arr_est : "");
  let midBadges = null;
  if (hasDep || hasArr) {
    if (depSrc && depSrc === arrSrc) {
      const lab = depSrc === "amadeus" ? "计划时刻"
        : (depSrc === "airport-board-x" ? "跨日班期" : "计划时刻");
      midBadges = timeSrcBadge(lab, depSrc);
    } else {
      midBadges = (
        <span>
          {timeSrcBadge("起飞", depSrc)}
          {timeSrcBadge("落地", arrSrc)}
        </span>
      );
    }
  }
  return (
    <div class="card">
      <div class="card-head">
        <div class="dd-title">
          <h3>{d.date} {weekday(d.date)}</h3>
          <span class="price">含税 {fmtMoney(d.total_price)}</span>
          <span class={"badge " + (below ? "green" : "gray")}>{below ? "低于心理价位" : "高于心理价位"}</span>
          {srcBadge(d)}
        </div>
      </div>
      <div class="ft-line">
        <div class="ft-endpoint">
          <div class={"ft-time" + (hasDep ? "" : " unknown")}>{d.dep_time || "--:--"}</div>
          <div class="ft-code">{route.from_iata || route.from_city}</div>
        </div>
        <div class="ft-mid">
          <div>
            <span class="ft-dur">
              {connecting ? "中转 · " + (d.duration_text || "全程时刻待查") : (d.duration_text || "飞行时长待查")}
            </span>
            {midBadges}
            {d.stop_kind && (d.stop_city || d.stop_arr) ? (
              <div class="ft-stop">
                {(d.stop_kind === "transfer" ? "中转 " : "经停 ") + (d.stop_city || "中转城市")}
                {d.stop_arr ? " · " + d.stop_arr + " 到" : ""}
              </div>
            ) : null}
          </div>
          <div class="ft-path"><span class="ft-plane">✈</span></div>
          {!hasDep && !hasArr && alts.length > 0 && (
            <div>
              <span class="ft-alts-label">当日参考班次</span>
              {alts.map((a) => (
                <span
                  class={"ft-alt" + (a.exact ? "" : " x")}
                  title={a.exact ? "出发机场该航线当日星期实测时刻" : "同一航班其他班期时刻, 同航季通常一致, 仅供参考"}
                >
                  {a.no} {a.dep}
                </span>
              ))}
            </div>
          )}
          {!hasDep && !hasArr && alts.length === 0 && (
            <div class="ft-pend">时刻待班期库覆盖 · 以购票页为准</div>
          )}
          {hasDep !== hasArr && <div class="ft-pend">另一段时刻待班期库覆盖</div>}
        </div>
        <div class="ft-endpoint">
          <div
            class={"ft-time" + (hasArr ? "" : (hasEst ? " est" : " unknown"))}
            title={hasEst ? "按同航线真实飞行时长推算(到达板实测中位数)" : ""}
          >
            {hasArr ? d.arr_time : (hasEst ? "~" + d.arr_est : "--:--")}
            {shownArr && d.dep_time && shownArr < d.dep_time ? (
              <span class="ft-nextday" title="跨零点航班 · 次日到达">+1d</span>
            ) : null}
          </div>
          <div class="ft-code">{route.to_iata || route.to_city}</div>
        </div>
      </div>
      <div class="dd-meta">
        {isRT
          ? "去程 " + (d.flight_no || d.airline) + " ¥" + Math.round(d.out_total) +
            " + 返程 " + fmtMD(d.ret_date) + " " + (d.ret_flight || d.airline) +
            " ¥" + Math.round(d.ret_total) + " = " + fmtMoney(d.total_price) + warn + (d.baggage || "")
          : (d.flight_no ? d.flight_no + " " : "") + (d.airline || "") + " · 裸价 " + fmtMoney(d.bare_price) +
            " + 机建燃油 = " + fmtMoney(d.total_price) + warn + (d.baggage || "")}
        {d.alert ? <span class="badge green">已推送提醒</span> : null}
      </div>
      {(d.source === "nearby-ref" || d.source === "interp") && (
        <div class="dd-meta">
          <span class="dd-hint">
            {d.source === "nearby-ref"
              ? "该日期源端无缓存价, 显示" + (d.ref_offset ? "距此 " + d.ref_offset + " 天的最近有价日参考" : "最近有价日的参考价") + " · 点击下方按钮直达查当日实际价格"
              : "该日期源端无缓存价, 价格为两侧真实价插值估算" + (d.flight_no ? " · 参考航班 " + d.flight_no + "(时刻以购票页为准)" : "") + " · 点击下方按钮直达查当日实际价格"}
          </span>
        </div>
      )}
      {tr.second && (
        <div class="dd-meta muted">
          参考: {tr.second.train_code} 二等 {fmtMoney(trainSeats(tr.second)["二等座"])} / 学生≈
          {fmtMoney(trainSeats(tr.second)["二等座"] * 0.75)} ({tr.second.pair.replace("-", "→")} {tr.second.dep_time}出发)
        </div>
      )}
      <div class="dd-actions">
        <a class="btn primary small" href={d.url} target="_blank" rel="noopener">直达购票页 →</a>
      </div>
    </div>
  );
}
