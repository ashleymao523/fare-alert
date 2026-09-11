import { useEffect, useState } from "preact/hooks";
import { reverseSearch, fetchCities, fetchSnapshot } from "../lib/api.js";
import AcField from "./AcField.jsx";

export default function ReverseView() {
  const [from, setFrom] = useState("杭州");
  const [budget, setBudget] = useState(500);
  const [days, setDays] = useState(30);
  const [maxReq, setMaxReq] = useState(8);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetchSnapshot()
      .then((s) => {
        const r0 = (s && s.routes && s.routes[0]);
        if (r0 && r0.from_city) setFrom(r0.from_city);
      })
      .catch(() => {});
  }, []);
  const scan = () => {
    const fc = (from || "").trim();
    if (!fc) { setErr("请先填写出发城市"); return; }
    setBusy(true); setErr(""); setRes(null);
    reverseSearch({ from_city: fc, budget: parseFloat(budget) || 0,
                    days: parseInt(days, 10) || 30,
                    max_requests: parseInt(maxReq, 10) || 8 })
      .then((result) => setRes(result))
      .catch((e) => setErr("扫描失败: " + (e.message || e)))
      .finally(() => setBusy(false));
  };
  return (
    <div>
      <div class="card">
        <div class="card-head">
          <h3>🧭 预算找目的地</h3>
          <span class="sub">¥X 以内从 A 出发能去哪 · 结果缓存 6 小时</span>
        </div>
        <div class="rev-form2">
          <AcField label="出发城市" value={from} ensure={fetchCities}
            placeholder="出发城市, 如 杭州" onChange={setFrom} classExtra="grow2" />
          <label class="field2">
            <span class="f-label2">预算(含税总价)</span>
            <div class="th-wrap">
              <input type="number" min="50" value={budget}
                onInput={(e) => setBudget(e.target.value)} />
              <div class="chiplets">
                {[300, 500, 800, 1200].map((v) => (
                  <button key={v} type="button" class="chiplet"
                    onClick={() => setBudget(v)}>¥{v}</button>
                ))}
              </div>
            </div>
          </label>
          <label class="field2">
            <span class="f-label2">未来天数</span>
            <select value={days} onChange={(e) => setDays(e.target.value)}>
              <option value="15">15天</option>
              <option value="30">30天</option>
              <option value="60">60天</option>
            </select>
          </label>
          <label class="field2">
            <span class="f-label2">请求预算</span>
            <select value={maxReq} onChange={(e) => setMaxReq(e.target.value)}>
              <option value="4">4 个(最快)</option>
              <option value="8">8 个(默认)</option>
              <option value="12">12 个</option>
              <option value="15">15 个(上限)</option>
            </select>
          </label>
          <button class="btn primary" disabled={busy} onClick={scan}>
            {busy ? "扫描中…(约" + (parseInt(maxReq, 10) * 2) + "秒)" : "🧭 扫描可去目的地"}
          </button>
        </div>
        <div class="muted rev-note2">
          每次扫描按候选城市逐个查价格日历; 结果缓存 6 小时,
          缓存命中不消耗请求预算, 可逐步扩大扫描面。
        </div>
        {err ? <div class="warn-box">{err}</div> : null}
        {res ? (
          <div class="rev-meta2">
            扫描 {res.scanned}/{res.pool_size} 个候选 · 实发请求 {res.requests_used}
            · 失败 {res.failed} · 窗口 {res.window && res.window.from} ~ {res.window && res.window.to}
          </div>
        ) : null}
        {(res && res.hits && res.hits.length) ? res.hits.map((h, i) => (
          <div class="rev-hit2" key={h.city + String(h.date) + String(h.total_price)}>
            <span class="rev-rank2">{i + 1}</span>
            <div class="rev-main2">
              <div class="rev-city2">
                {h.city}
                <span class={"chip2" + (h.cached ? " plan" : " hero")}>
                  {h.cached ? "缓存" : "实时"}
                </span>
              </div>
              <div class="muted rev-sub2">
                {h.date} · {(h.airline || h.flight_no || "")}
                · 裸价¥{h.bare_price}+税费
              </div>
            </div>
            <div class="rev-price2">¥{h.total_price}</div>
            <a class="v-link2" href={h.url} target="_blank" rel="noopener">直达购票 →</a>
          </div>
        )) : (res && !err) ? (
          <div class="empty">
            未找到 ≤ ¥{budget} 的目的地: 试试提高预算、扩大天数, 或加大请求预算多扫几个候选。
          </div>
        ) : null}
      </div>
    </div>
  );
}
