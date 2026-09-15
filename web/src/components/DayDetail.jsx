import { useState, useEffect } from "react";
import { fmtMoney, fmtMD, weekday, trainSeats, trainBest, dealForDate } from "../lib/data.js";
import { fetchDaySchedule } from "../lib/api.js";

function srcBadge(d) {
  if (d.source === "qunar-intl") return <span class="badge sky">国际特价</span>;
  if (d.source === "amadeus-intl") return <span class="badge sky">Amadeus</span>;
  if (d.source === "amadeus-fill") return <span class="badge amber">Amadeus补</span>;
  if (d.source === "booking-ref") {
    return (
      <span class="badge sky" title="Booking.com 无key国际渠道参考价，通常高于国内OTA；待去哪儿日历生成缓存价后自动替换">
        Booking参考
      </span>
    );
  }
  if (d.source === "point-fill") return <span class="badge green">精点核价</span>;
  if (d.source === "nearby-ref") {
    return <span class="badge gray">{d.ref_offset ? "临近日参考 · 距" + d.ref_offset + "天" : "临近日参考"}</span>;
  }
  if (d.source === "interp") return <span class="badge amber">两侧真实价插值</span>;
  return null;
}

const DOW_CN = ["一", "二", "三", "四", "五", "六", "日"];

function borrowLabel(d) {
  const w = d && d.borrow_dow !== undefined && d.borrow_dow !== null
    ? String(d.borrow_dow) : "";
  return w && DOW_CN[+w] ? ("借周" + DOW_CN[+w]) : "跨日";
}

function timeSrcBadge(label, src, deal) {
  if (src === "airport-board") return <span class="badge gray ts-badge">{label}·班期精查</span>;
  if (src === "airport-board-x") {
    const d = deal || {};
    const tag = (d.borrow_dow !== undefined && d.borrow_dow !== null
      && String(d.borrow_dow) && DOW_CN[+d.borrow_dow])
      ? ("借周" + DOW_CN[+d.borrow_dow]) : "跨日";
    const votes = +d.borrow_votes || 0;
    const tip = d.borrow_unstable
      ? "该班次周内各天起飞时刻不一, 显示的是最接近的一条, 请以购票页当日列表为准"
      : (votes >= 2
        ? "同一航班号周内" + votes + "天时刻一致(稳定排班), 同航季通常可靠, 仅供参考; 班期库沉淀满7天后自动变为精查"
        : "同一航班号" + tag + "班期的时刻, 同航季通常一致, 仅供参考; 班期库沉淀满7天后自动变为精查");
    return (
      <span class="badge amber ts-badge" title={tip}>
        {label}·{tag}{d.borrow_unstable ? "?" : ""}参考
      </span>
    );
  }
  if (src === "alt-ref") {
    return (
      <span class="badge amber ts-badge" title="同航线当日参考班次时刻(非本航班号), 仅供参考">
        {label === "参考班次" ? "参考班次" : label + "·参考班次"}
      </span>
    );
  }
  if (src === "booking") {
    return (
      <span class="badge sky ts-badge" title="Booking.com 当日最低报价的完整行程: 航班号/起降时刻/托运额度均来自该报价">
        {label}·Booking精确
      </span>
    );
  }
  if (src === "booking-x") {
    return (
      <span class="badge amber ts-badge" title="价格行仍是权威数据源; 时刻取自Booking.com同日最低报价行程(航班号可能不同), 仅供参考">
        {label}·Booking同日参考
      </span>
    );
  }
  if (src === "amadeus") return <span class="badge sky ts-badge">{label}·Amadeus</span>;
  return null;
}

function dayListUrl(route, date) {
  // v0.70: any known deal url is the safest template (right city
  // spelling for intl hubs); swap goDate, else build from city names
  const pool = (route.deals || []).concat(route.return_deals || []);
  const base = pool.find((d) => d && d.url);
  if (base && base.url) {
    return base.url.replace(/([?&])goDate=[^&]*/, "$1goDate=" + date);
  }
  return "https://m.flight.qunar.com/ncs/page/flightlist?depCity="
    + encodeURIComponent(route.from_city || "")
    + "&arrCity=" + encodeURIComponent(route.to_city || "")
    + "&goDate=" + date + "&from=touch_index_search";
}

export default function DayDetail({ route, date }) {
  const [sched, setSched] = useState(null);
  useEffect(() => {
    // v0.69: per-date timetable strip - every flight the schedule
    // library knows for this route's weekday, zero extra key needed
    if (!route || !date) return undefined;
    let alive = true;
    setSched(null);
    fetchDaySchedule(route.from_city || "", route.to_city || "", date)
      .then((x) => { if (alive && x && x.ok) setSched(x); })
      .catch(() => {});
    return () => { alive = false; };
  }, [route && route.id, route && route.from_city,
      route && route.to_city, date]);
  const schedStrip = sched && sched.rows && sched.rows.length ? (
    <div class="dd-meta tl-box">
      <span class="ft-alts-label">
        当日班期表 · {sched.total || sched.rows.length}班 · 24小时时间线
      </span>
      <div class="tl-rail" aria-label="当日班次起降区间 24 小时分布">
        {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => (
          <span class="tl-tick" style={{ left: (h / 24 * 100) + "%" }} />
        ))}
        {[0, 6, 12, 18].map((h) => (
          <span class="tl-lab" style={{ left: (h / 24 * 100) + "%" }}>
            {String(h).padStart(2, "0")}
          </span>
        ))}
        <span class="tl-lab end">24</span>
        {sched.rows.map((a, i) => {
          const mm = ((parseInt((a.dep || "").slice(0, 2), 10) || 0) * 60)
            + (parseInt((a.dep || "").slice(3, 5), 10) || 0);
          const aH = parseInt((a.arr || "").slice(0, 2), 10);
          const aM = parseInt((a.arr || "").slice(3, 5), 10);
          const hasArr = !isNaN(aH) && !isNaN(aM);
          const am = hasArr ? (aH * 60 + aM) : 0;
          const depPct = Math.min(100, Math.max(0, mm / 1440 * 100));
          const tip = (a.src === "booking" ? "Booking当日实测·"
            : (a.exact ? "" : "参考·")) + a.no + " " + a.dep
            + (a.arr ? "→" + a.arr : "")
            + (a.dur ? " · 历时" + a.dur : "")
            + ((a.airline || a.craft)
              ? " · " + [a.airline, a.craft].filter(Boolean).join(" ")
              : "")
            + (a.via ? " · 经停" + a.via : "")
            + " · 点击直达去哪儿当日列表";
          if (!hasArr) {
            return (
              <a
                class={"tl-dot" + (a.exact ? "" : " x") + (i % 2 ? " up" : "")}
                style={{ left: depPct + "%" }}
                href={dayListUrl(route, date)}
                target="_blank"
                rel="noopener"
                title={tip}
              />
            );
          }
          // v0.75: dep->arr span bar; overnight flights clamp to 24:00.
          const span = am > mm ? (am - mm) : (1440 - mm);
          const wPct = Math.min(100 - depPct,
            Math.max(0.6, span / 1440 * 100));
          return (
            <a
              class={"tl-span" + (a.exact ? "" : " x") + (i % 2 ? " up" : "")}
              style={{ left: depPct + "%", width: wPct + "%" }}
              href={dayListUrl(route, date)}
              target="_blank"
              rel="noopener"
              title={tip + (am <= mm ? " · 次日到达" : "")}
            />
          );
        })}
      </div>
      {sched.rows.map((a) => (
        <a
          class={"ft-alt" + (a.exact ? "" : " x")}
          href={dayListUrl(route, date)}
          target="_blank"
          rel="noopener"
          title={(a.exact
            ? "该航班当日星期有班期实录: 起飞→落地"
            : "同号航班其他班期时刻, 同航季通常一致, 仅供参考")
            + (a.dur ? " · 历时" + a.dur : "")
            + ((a.airline || a.craft)
              ? " · " + [a.airline, a.craft].filter(Boolean).join(" ")
              : "")
            + (a.via ? " · 经停" + a.via : "")
            + " · 点击直达去哪儿当日列表"}
        >
          {a.no} {a.dep}{a.arr ? "→" + a.arr : ""}
          {a.dur ? <span class="ft-alt-craft">{a.dur}</span> : null}
          {a.craft ? <span class="ft-alt-craft">{a.craft.split("(")[0]}</span> : null}
          {!a.arr && a.via ? <span class="ft-alt-craft">经停{a.via}</span> : null}
        </a>
      ))}
      {sched.has_more && (
        <a
          class="ft-alt x"
          href={dayListUrl(route, date)}
          target="_blank"
          rel="noopener"
          title={"班期过多, 此处展示前30班 · 点击直达去哪儿当日列表查看全部"}
        >
          +另有{(sched.total || sched.rows.length) - sched.rows.length}班
        </a>
      )}
    </div>
  ) : null;
  if (!route || !date) return null;
  const d = dealForDate(route, date);
  const tr = trainBest(route);
  if (!d) {
    return (
      <div class="card">
        <div class="dd-title">{date} {weekday(date)} · 该日无报价</div>
        {schedStrip}
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
  const isRef = d.source === "nearby-ref" || d.source === "interp";
  const shownArr = hasArr ? d.arr_time : (hasEst ? d.arr_est : "");
  const SEASON_SWITCH = "2026-10-25"; // winter schedule rollover
  let midBadges = null;
  if (hasDep || hasArr) {
    if (depSrc && depSrc === arrSrc) {
      const lab = depSrc === "amadeus" ? "计划时刻"
        : (depSrc === "airport-board-x" ? (borrowLabel(d) + "班期")
          : (depSrc === "alt-ref" ? "参考班次"
            : ((depSrc === "booking" || depSrc === "booking-x")
              ? "当日行程" : "计划时刻")));
      midBadges = timeSrcBadge(lab, depSrc, d);
    } else {
      midBadges = (
        <span>
          {timeSrcBadge("起飞", depSrc, d)}
          {timeSrcBadge("落地", arrSrc, d)}
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
          <div class={"ft-time" + (hasDep ? "" : " unknown")}>{d.dep_time || (isRef ? "参考价" : "--:--")}</div>
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
          {alts.some((a) => a.src === "booking") && (
            <div>
              <span class="ft-alts-label"
                title="Booking.com 该日期实测报价航班的精确起降时刻(非星期推断)">
                当日实测班次 · {alts.filter((a) => a.src === "booking").length}班
              </span>
              {alts.filter((a) => a.src === "booking").map((a) => {
                // v0.92: the OTA cheapest flight of this date, when it
                // also appears in the measured timetable, gets a badge -
                // price + exact time + deep link in one chip.
                const best = (d.flight_no || "").trim() && a.no === d.flight_no.trim();
                return (
                  <a
                    class={"ft-alt" + (best ? " best" : "")}
                    href={dayListUrl(route, date)}
                    target="_blank"
                    rel="noopener"
                    title={"Booking当日实测 " + a.no + " " + a.dep
                      + (a.arr ? "→" + a.arr : "")
                      + (a.dur ? " · 历时" + a.dur : "")
                      + ((a.airline || a.craft)
                        ? " · " + [a.airline, a.craft].filter(Boolean).join(" ")
                        : "")
                      + (a.via ? " · 经停" + a.via : "")
                      + (best ? " · 本日最低价航班" : "")
                      + " · 点击直达去哪儿当日列表购票"}
                  >
                    {best ? <span class="ft-best">低价</span> : null}
                    {a.no} {a.dep}{a.arr ? "→" + a.arr : ""}
                    {a.craft ? <span class="ft-alt-craft">{a.craft.split("(")[0]}</span> : null}
                  </a>
                );
              })}
            </div>
          )}
          {!hasDep && !hasArr && !alts.some((a) => a.src === "booking") && alts.length > 0 && (
            <div>
              <span class="ft-alts-label">当日参考班次</span>
              {alts.map((a) => (
                <span
                  class={"ft-alt" + (a.exact ? "" : " x")}
                  title={a.exact ? "出发机场该航线当日星期实测时刻" : "同一航班其他班期时刻, 同航季通常一致, 仅供参考"}
                >
                  {a.no} {a.dep}{a.arr ? "→" + a.arr : ""}
                  {a.craft ? <span class="ft-alt-craft">{a.craft.split("(")[0]}</span> : null}
                </span>
              ))}
            </div>
          )}
          {!hasDep && !hasArr && alts.length === 0 && (
            <div class="ft-pend">
              {isRef
                ? "参考价 · 非当日可售航班, 无对应时刻"
                : d.date >= SEASON_SWITCH
                  ? "换季班期待收录 · 持续运行自动补全"
                  : "班期库暂未覆盖 · 持续运行自动补全"}
            </div>
          )}
          {hasDep !== hasArr && (
            <div class="ft-pend">
              {!hasDep && connecting
                ? "首段班期待覆盖 · 以购票页为准"
                : (hasDep && connecting
                  ? "中转段不经杭州板 · 落地以购票页为准"
                  : "另一段时刻待班期库覆盖")}
            </div>
          )}
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
      {schedStrip}
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
        <a
          class={"btn primary small" + (!hasDep && !hasArr && !isRef ? " amber-cta" : "")}
          href={d.url}
          target="_blank"
          rel="noopener"
          title={!hasDep && !hasArr && !isRef
            ? "本行时刻待班期库沉淀 · 点击直达去哪儿当日航班列表, 起降时刻以列表页为准"
            : "直达去哪儿当日航班列表购票"}
        >
          {!hasDep && !hasArr && !isRef ? "查当日实时班次与购票 →" : "直达购票页 →"}
        </a>
      </div>
    </div>
  );
}
