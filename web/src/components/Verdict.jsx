import { fmtMoney, fmtMD, trainSeats, studentEst, cheapestFlight, trainBest } from "../lib/data.js";

function Vcard({ isBest, title, price, sub, url }) {
  return (
    <div class={"vcard" + (isBest ? " best" : "")}>
      {isBest && <div class="v-tag">最优</div>}
      <div class="v-title">{title}</div>
      <div class="v-price">{price}</div>
      <div class="v-sub">{sub}</div>
      {url && <a class="v-link" href={url} target="_blank" rel="noopener">去查票/下单 →</a>}
    </div>
  );
}

export default function Verdict({ route }) {
  if (!route || !route.deals || !route.deals.length) return null;
  const f = cheapestFlight(route);
  const isRT = !!(route.trip_type === "roundtrip" && route.combined);
  const cb = route.combined;
  const tr = trainBest(route);
  const t = tr.second;
  const ze = t ? trainSeats(t)["二等座"] : null;
  const s = t ? ze * 0.75 : null;
  const sl = tr.sleeper;
  const names = { flight: "✈️ 机票", train: "🚄 动车二等座", student: "🎓 学生动车", sleeper: "🛏️ 列车卧铺" };
  const flightPrice = isRT ? cb.total : f.total_price;
  const cands = [{ k: "flight", p: flightPrice }];
  if (t) cands.push({ k: "train", p: ze });
  if (t) cands.push({ k: "student", p: s });
  if (sl) cands.push({ k: "sleeper", p: sl.price });
  cands.sort((a, b) => a.p - b.p);
  const winner = cands[0].k;
  const save = cands.length > 1 ? cands[1].p - cands[0].p : null;
  const saveTxt = save != null ? ", 比次优方案节省约" + fmtMoney(save) : "";
  const slStu = sl ? studentEst(trainSeats(sl.train)) : null;
  return (
    <div>
      <div class="verdict-banner">
        <b>当前最优: {names[winner]}</b>{saveTxt}。时间为参考: 飞机含提前值机1-5小时; 动车历时8-15小时, 卧铺朝发夕至可车上过夜省一晚住宿。
      </div>
      <div class="verdict-cards">
        <Vcard
          isBest={winner === "flight"}
          title={isRT
            ? "✈️ 往返最低 (" + fmtMD(cb.out_date) + "⇄" + fmtMD(cb.ret_date) + ")"
            : "✈️ 最低机票 (" + f.date + ")"}
          price={fmtMoney(flightPrice)}
          sub={isRT
            ? <span>去程 {cb.out_flight || f.airline} ¥{Math.round(cb.out_total)} + 返程 {cb.ret_flight || f.airline} ¥{Math.round(cb.ret_total)} = 合计<br />行李: {f.baggage}<br />两段分别下单, 起降时刻以订单页为准</span>
            : <span>{(f.flight_no ? f.flight_no + " " : "") + f.airline} · 裸价{fmtMoney(f.bare_price)}+税费{f.source === "amadeus-fill" ? " · Amadeus补" : ""}<br />行李: {f.baggage}<br />起降时刻/飞行时长以下单页为准</span>}
          url={isRT ? (cb.url || f.url) : f.url}
        />
        {t && (
          <Vcard
            isBest={winner === "train"}
            title={"🚄 动车二等 (" + t.train_code + ")"}
            price={fmtMoney(ze)}
            sub={<span>{t.pair.replace("-", " → ")} · {t.dep_time}-{t.arr_time} 历时{t.duration_text}</span>}
            url={t.url}
          />
        )}
        {t && (
          <Vcard
            isBest={winner === "student"}
            title="🎓 学生动车 ≈"
            price={fmtMoney(s)}
            sub="二等座公布票价75折估算 · 资格/优惠区间以12306下单页为准"
            url={t.url}
          />
        )}
        {sl && (
          <Vcard
            isBest={winner === "sleeper"}
            title={"🛏️ 卧铺 (" + sl.train.train_code + " " + sl.label + ")"}
            price={fmtMoney(sl.price)}
            sub={<span>{sl.train.pair.replace("-", " → ")} · {sl.train.dep_time}-{sl.train.arr_time} 历时{sl.train.duration_text}{slStu != null ? <br /> : null}{slStu != null ? "学生卧铺≈" + fmtMoney(slStu) : ""}</span>}
            url={sl.train.url}
          />
        )}
      </div>
    </div>
  );
}
