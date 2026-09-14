import { useEffect, useState } from "preact/hooks";
import { saveConfig } from "../lib/api.js";

const fmt = (n) => (typeof n === "number" ? "¥" + Math.round(n) : "-");
const splitCities = (t) =>
  String(t || "").split(/[、,,\n]/).map((s) => s.trim()).filter(Boolean);

function Spark({ obs }) {
  const pts = (obs || []).slice(-10).map((o) => o.price)
    .filter((n) => typeof n === "number");
  if (pts.length < 2) return <span class="muted">-</span>;
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
      class="cabin-spark" aria-hidden="true">
      <path class="spark-line" d={d} />
      <circle cx={x(minI)} cy={y(min)} r="2.6" class="spark-min" />
    </svg>
  );
}

export default function CabinCard({ cfg, setCfg }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const load = () => {
    fetch("/api/cabin")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setErr(String(e)));
  };
  useEffect(load, []);
  if (err) return null;
  if (!data) return null;
  const cw = data.config || {};
  const live = (cfg && cfg.cabin_watch) || {};
  const setD = (k, v) => setDraft(Object.assign({}, draft, { [k]: v }));

  const startEdit = () => {
    setEditing(true);
    setMsg("");
    setDraft({
      enabled: live.enabled != null ? !!live.enabled : !!cw.enabled,
      default_to_city: live.default_to_city || cw.default_to_city || "杭州",
      threshold_total: live.threshold_total || cw.threshold_total || 1500,
      cooldown_hours:
        live.cooldown_hours != null ? live.cooldown_hours
          : (cw.cooldown_hours != null ? cw.cooldown_hours : 12),
      fromText: (live.watch_from_cities || []).join("、"),
    });
  };
  const cancelEdit = () => { setEditing(false); setMsg(""); };
  const doSave = () => {
    const cities = splitCities(draft.fromText);
    const nextCw = {
      enabled: !!draft.enabled,
      cabins: (live.cabins && live.cabins.length) ? live.cabins : ["business"],
      default_to_city: (draft.default_to_city || "").trim() || "杭州",
      threshold_total: Number(draft.threshold_total) || 1500,
      cooldown_hours: Number(draft.cooldown_hours) || 0,
      watch_from_cities: cities,
    };
    const next = Object.assign({}, cfg, { cabin_watch: nextCw });
    setBusy(true);
    setMsg("保存中…");
    setCfg(next);
    saveConfig(next)
      .then((r) => {
        setCfg(r.config);
        setEditing(false);
        setMsg("已保存 ✅ 下轮抓取生效");
        load();
      })
      .catch((e) => setMsg("保存失败: " + (e.message || e)))
      .finally(() => setBusy(false));
  };

  const routes = (data.history && data.history.routes) || {};
  const rows = Object.entries(routes)
    .map(([id, r]) => ({ id, ...r, n: (r.obs || []).length }))
    .sort((a, b) => (a.lowest || 1e9) - (b.lowest || 1e9));
  return (
    <div class="card">
      <div class="card-head">
        <h3>公务舱低价监控</h3>
        <div class="head-actions">
          <span class={"badge " + (cw.enabled ? "green" : "gray")}>
            {cw.enabled ? "运行中" : "未启用"}
          </span>
          <button class="btn sm" onClick={editing ? cancelEdit : startEdit}>
            {editing ? "取消" : "编辑"}
          </button>
        </div>
      </div>
      {editing ? (
        <div class="cabin-edit">
          <div class="push-grid">
            <label class="field2">
              <span class="f-label2">启用监控</span>
              <input type="checkbox" checked={!!draft.enabled}
                onChange={(e) => setD("enabled", e.target.checked)} />
            </label>
            <label class="field2">
              <span class="f-label2">目的地城市</span>
              <input type="text" value={draft.default_to_city}
                onInput={(e) => setD("default_to_city", e.target.value)} />
            </label>
            <label class="field2">
              <span class="f-label2">心理价位 (总价)</span>
              <input type="number" min="1" value={draft.threshold_total}
                onInput={(e) => setD("threshold_total", e.target.value)} />
            </label>
            <label class="field2">
              <span class="f-label2">提醒冷却 (小时)</span>
              <input type="number" min="0" value={draft.cooldown_hours}
                onInput={(e) => setD("cooldown_hours", e.target.value)} />
            </label>
          </div>
          <label class="field2">
            <span class="f-label2">
              监控出发城市 (顿号/逗号/换行分隔, 留空 = 路线内全部出发地)
            </span>
            <textarea rows="2" value={draft.fromText}
              onInput={(e) => setD("fromText", e.target.value)} />
          </label>
          <div class="row-btns">
            <button class="btn primary" disabled={busy} onClick={doSave}>
              保存监控配置
            </button>
            {msg ? <span class="muted push-msg">{msg}</span> : null}
          </div>
        </div>
      ) : (
        <div>
          <div class="cabin-meta">
            目的地 {cw.default_to_city || "杭州"} · 阈值 {fmt(cw.threshold_total)} ·
            冷却 {(cw.cooldown_hours || 0) + "h"}
            {(cw.watch_from_cities || []).length
              ? " · 出发地 " + cw.watch_from_cities.join("/") : ""}
          </div>
          {rows.length ? (
            <table class="tbl">
              <thead>
                <tr><th>出发</th><th>到达</th><th>历史最低</th><th>走势</th><th>样本</th><th>状态</th></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.from_city}</td>
                    <td>{r.to_city}</td>
                    <td class="price">{fmt(r.lowest)}</td>
                    <td><Spark obs={r.obs} /></td>
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
                : "点击右上「编辑」开启后, 各出发地飞 " + (cw.default_to_city || "杭州") + " 的公务舱最低价会在此汇总"}
            </div>
          )}
          {data.last_alert ? (
            <div class="cabin-last">
              最近提醒: {data.last_alert.from_city}到{data.last_alert.to_city} ·
              {data.last_alert.date} · {fmt(data.last_alert.price)}
            </div>
          ) : null}
          {msg && !editing ? <div class="muted push-msg">{msg}</div> : null}
        </div>
      )}
    </div>
  );
}
