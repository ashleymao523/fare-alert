import { fmtMoney, trainSeats, studentEst, trainMinPrice, trainBest, collectTrains } from "../lib/data.js";

export default function Trains({ route }) {
  if (!route || !route.train || !route.train.pairs) {
    return (
      <div class="card">
        <div class="card-head"><h3>🚄 动车对比 (12306)</h3></div>
        <div class="empty">未启用列车对比或暂无数据 (可在经典版线路管理中开启)</div>
      </div>
    );
  }
  const tr = trainBest(route);
  const sorted = tr.all.slice().sort((a, b) => (trainMinPrice(a) || 9e9) - (trainMinPrice(b) || 9e9));
  const minP = sorted.length ? trainMinPrice(sorted[0]) : null;
  return (
    <div class="card">
      <div class="card-head">
        <h3>🚄 动车对比 (12306)</h3>
        <span class="sub">查询日 {route.train.query_date} · 更新于 {String(route.train.updated_at || "").replace("T", " ")}</span>
      </div>
      {tr.errors.map((e) => <div class="err-line">⚠️ {e}</div>)}
      {!sorted.length ? <div class="empty">未查到车次</div> : (
        <div class="tbl-scroll">
          <table class="tbl">
            <thead>
              <tr><th>车次</th><th>区间</th><th>时刻</th><th>历时</th><th>席位票价(12306查到即列)</th><th>学生≈</th><th>购票</th></tr>
            </thead>
            <tbody>
              {sorted.slice(0, 20).map((t) => {
                const seats = trainSeats(t);
                const keys = Object.keys(seats).sort((a, b) => seats[a] - seats[b]);
                const stu = studentEst(seats);
                const low = trainMinPrice(t) != null && trainMinPrice(t) === minP;
                return (
                  <tr class={low ? "cheap-row" : ""}>
                    <td><b>{t.train_code}</b></td>
                    <td>{(t.pair || "").replace("-", " → ")}</td>
                    <td>{t.dep_time} - {t.arr_time}</td>
                    <td>{t.duration_text}</td>
                    <td>
                      <div class="seat-cell">
                        {keys.length
                          ? keys.map((lab) => (
                              <span class={"seat-chip" + (lab.indexOf("卧") >= 0 ? " sleep" : "")}>
                                {lab} {fmtMoney(seats[lab])}
                              </span>
                            ))
                          : <span class="muted">--</span>}
                      </div>
                    </td>
                    <td>{stu != null ? fmtMoney(stu) : "--"}</td>
                    <td>
                      {t.url
                        ? <a class="btn small" href={t.url} target="_blank" rel="noopener">下单</a>
                        : "--"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div class="muted" style={{ marginTop: "var(--sp-md)", fontSize: "var(--fs-sm)" }}>
        含高铁/动车/直达/特快等列车 · 12306查到什么席位就列什么 · 含卧铺 · 学生票估算: 动车组二等座75折 普速硬卧=硬卧-硬座半价 · 12306数据缓存24小时
      </div>
    </div>
  );
}
