import { useEffect, useState } from "preact/hooks";

const fmt = (n) => (typeof n === "number" ? "¥" + Math.round(n) : "-");

export default function CabinCard() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    fetch("/api/cabin")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);
  if (err) return null;
  if (!data) return null;
  const cw = data.config || {};
  const routes = (data.history && data.history.routes) || {};
  const rows = Object.entries(routes)
    .map(([id, r]) => ({ id, ...r, n: (r.obs || []).length }))
    .sort((a, b) => (a.lowest || 1e9) - (b.lowest || 1e9));
  return (
    <div class="card">
      <div class="card-head">
        <h3>公务舱低价监控</h3>
        <span class={"badge " + (cw.enabled ? "green" : "gray")}>
          {cw.enabled ? "运行中" : "未启用"}
        </span>
      </div>
      <div class="cabin-meta">
        目的地 {cw.default_to_city || "杭州"} · 阈值 {fmt(cw.threshold_total)} ·
        冷却 {(cw.cooldown_hours || 0) + "h"}
      </div>
      {rows.length ? (
        <table class="tbl">
          <thead>
            <tr><th>出发</th><th>到达</th><th>历史最低</th><th>样本</th><th>状态</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.from_city}</td>
                <td>{r.to_city}</td>
                <td class="price">{fmt(r.lowest)}</td>
                <td>{r.n}</td>
                <td>
                  <span class={"badge " + (r.lowest <= (cw.threshold_total || 0) ? "green" : "gray")}>
                    {r.lowest <= (cw.threshold_total || 0) ? "低于阈值" : "观察中"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div class="empty">
          {cw.enabled
            ? "暂无公务舱样本 · 需配置 Amadeus 密钥后自动采集 (推送页可测)"
            : "在 config.json 的 cabin_watch 中开启后, 各出发地飞 " + (cw.default_to_city || "杭州") + " 的公务舱最低价会在此汇总"}
        </div>
      )}
      {data.last_alert ? (
        <div class="cabin-last">
          最近提醒: {data.last_alert.from_city}到{data.last_alert.to_city} ·
          {data.last_alert.date} · {fmt(data.last_alert.price)}
        </div>
      ) : null}
    </div>
  );
}
