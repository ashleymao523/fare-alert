import { useEffect, useState } from "preact/hooks";
import { fmtMD, weekday } from "../lib/data.js";
import { fetchDestIntel } from "../lib/api.js";

export default function DestIntel({ route }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    let alive = true;
    setData(null);
    setErr(false);
    if (route) {
      fetchDestIntel(route.id)
        .then((j) => { if (alive) setData(j && j.ok ? j : null); })
        .catch(() => { if (alive) setErr(true); });
    }
    return () => { alive = false; };
  }, [route && route.id]);
  if (!route) return null;
  return (
    <div class="card">
      <div class="card-head">
        <h3>📍 目的地情报 · {route.to_city}</h3>
        <span class="sub">天气/汇率 · 开放API实时获取 · 免key</span>
      </div>
      {err ? <div class="empty">情报服务暂不可达</div> : null}
      {data && data.weather && data.weather.length ? (
        <div>
          <div class="intel-title">未来7天天气</div>
          <div class="wx-strip">
            {data.weather.map((w) => (
              <div class="wx-day">
                <span class="wx-ico">{w.icon}</span>
                <span class="wx-t"><b>{w.hi}°</b>/{w.lo}°</span>
                <span class="wx-date">{fmtMD(w.date)} {weekday(w.date)}</span>
                <span class="wx-label">{w.label}{w.pop && w.pop >= 30 ? " ·雨" + w.pop + "%" : ""}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {data && data.fx ? (
        <div class="fx-line">
          💱 参考汇率: <b>¥1000 ≈ {data.fx.per_1000} {data.fx.currency}</b>
          <span class="muted"> · open.er-api.com 每日更新</span>
        </div>
      ) : null}
      {data && !data.weather && !data.fx && !err ? <div class="empty">暂无情报数据</div> : null}
      {!data && !err ? <div class="empty">加载中…</div> : null}
    </div>
  );
}
