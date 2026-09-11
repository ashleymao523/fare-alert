import { useState } from "preact/hooks";
import { saveConfig, fetchCities, fetchStations } from "../lib/api.js";
import AcField from "./AcField.jsx";

const ROUTE_TPLS = [
  { from: "杭州", to: "重庆", th: 500, pairs: [["杭州东", "重庆北"]] },
  { from: "重庆", to: "杭州", th: 500, pairs: [["重庆北", "杭州东"]] },
  { from: "杭州", to: "成都", th: 450, pairs: [["杭州东", "成都东"]] },
  { from: "成都", to: "杭州", th: 450, pairs: [["成都东", "杭州东"]] },
  { from: "杭州", to: "西安", th: 500, pairs: [["杭州东", "西安北"]] },
  { from: "杭州", to: "北京", th: 600, pairs: [["杭州东", "北京南"]] },
];

function cleanCfgForSave(cfg) {
  const c = JSON.parse(JSON.stringify(cfg));
  c.routes.forEach((r, i) => {
    r.from_city = (r.from_city || "").trim();
    r.to_city = (r.to_city || "").trim();
    if (!r.from_city || !r.to_city) {
      throw new Error("线路 " + (i + 1) + " 的出发/到达城市未填写");
    }
    r.trip_type = r.trip_type === "roundtrip" ? "roundtrip" : "oneway";
    r.intl = !!r.intl;
    r.from_iata = (r.from_iata || "").trim().toUpperCase();
    r.to_iata = (r.to_iata || "").trim().toUpperCase();
    if (r.intl && !(r.from_iata && r.to_iata)) {
      throw new Error("线路 " + (i + 1) + " 启用国际航线需填写出发/到达IATA三字码");
    }
    const tc = r.train_compare || {};
    tc.station_pairs = (tc.station_pairs || []).filter(
      (p) => (p[0] || "").trim() && (p[1] || "").trim());
    r.train_compare = tc;
  });
  return c;
}

function RouteCard({ r, idx, update, remove }) {
  const setTC = (patch) => update({
    train_compare: Object.assign(
      { enabled: true, station_pairs: [] }, r.train_compare, patch),
  });
  const tc = r.train_compare || { enabled: true, station_pairs: [] };
  if (!tc.station_pairs) tc.station_pairs = [];
  const setPair = (pi, pos, v) => {
    const pairs = tc.station_pairs.map((p, i) =>
      i === pi ? (pos === 0 ? [v, p[1]] : [p[0], v]) : p.slice());
    setTC({ station_pairs: pairs });
  };
  const title = r.from_city + (r.trip_type === "roundtrip" ? " ⇄ " : " → ") + r.to_city;
  const swap = () => update({
    from_city: r.to_city, to_city: r.from_city,
    from_iata: r.to_iata || "", to_iata: r.from_iata || "",
  });
  return (
    <div class="rcard">
      <div class="rcard-head">
        <div class="rcard-title">{title}</div>
        <span class="rcard-id muted">{r.id}</span>
        <button class="btn danger sm" onClick={() => {
          if (window.confirm("确定删除线路 " + title + " ?")) remove();
        }}>删除</button>
      </div>
      <div class="rcard-grid">
        <AcField label="出发城市" value={r.from_city} ensure={fetchCities}
          placeholder="如 杭州 / hangzhou"
          onChange={(v) => update({ from_city: v })} />
        <button class="swap2" title="互换出发/到达" onClick={swap}>⇄</button>
        <AcField label="到达城市" value={r.to_city} ensure={fetchCities}
          placeholder="如 重庆 / chongqing"
          onChange={(v) => update({ to_city: v })} />
      </div>
      <div class="rcard-grid opts">
        <label class="field2">
          <span class="f-label2">行程类型</span>
          <select value={r.trip_type === "roundtrip" ? "roundtrip" : "oneway"}
            onChange={(e) => update({ trip_type: e.target.value })}>
            <option value="oneway">单程</option>
            <option value="roundtrip">往返(去+返合计比价)</option>
          </select>
        </label>
        <label class="field2 chk2">
          <span class="f-label2">国际航线(Amadeus)</span>
          <input type="checkbox" checked={!!r.intl}
            onChange={(e) => update({ intl: e.target.checked })} />
        </label>
        <label class="field2 iata2">
          <span class="f-label2">出发IATA</span>
          <input type="text" maxLength="3" placeholder="如 HGH" class="upper2"
            value={r.from_iata || ""}
            onInput={(e) => update({ from_iata: e.target.value.trim().toUpperCase() })} />
        </label>
        <label class="field2 iata2">
          <span class="f-label2">到达IATA</span>
          <input type="text" maxLength="3" placeholder="如 NRT" class="upper2"
            value={r.to_iata || ""}
            onInput={(e) => update({ to_iata: e.target.value.trim().toUpperCase() })} />
        </label>
      </div>
      <div class="rcard-grid nums">
        <label class="field2">
          <span class="f-label2">查询窗口(天)</span>
          <input type="number" min="1" max="60" value={r.window_days}
            onInput={(e) => {
              const v = parseInt(e.target.value, 10);
              if (!isNaN(v)) update({ window_days: v });
            }} />
        </label>
        <label class="field2">
          <span class="f-label2">{r.trip_type === "roundtrip"
            ? "心理价位·往返合计含税(元)" : "心理价位·含税总价(元)"}</span>
          <div class="th-wrap">
            <input type="number" min="0" value={r.threshold_total}
              onInput={(e) => {
                const v = parseFloat(e.target.value);
                if (!isNaN(v)) update({ threshold_total: v });
              }} />
            <div class="chiplets">
              {[300, 400, 500, 600].map((v) => (
                <button key={v} type="button" class="chiplet"
                  onClick={() => update({ threshold_total: v })}>¥{v}</button>
              ))}
            </div>
          </div>
        </label>
      </div>
      <div class="muted pair-hint2">
        国际线走 Amadeus 含税价; 往返 = 去程+返程合计对比阈值; 12306 车站对仅国内线生效
      </div>
      <div class="pair-sec">
        <div class="pair-head2">
          <span>🚄 列车对比 (12306·全席位)</span>
          <label class="chk-inline">
            <input type="checkbox" checked={tc.enabled !== false}
              onChange={(e) => setTC({ enabled: e.target.checked })} /> 启用
          </label>
        </div>
        <div class="muted pair-hint2">
          车站从12306车站库联想选择(中文/拼音均可, 如 hzd→杭州东); 选择即精确匹配,
          不会因手输偏差走模糊搜索
        </div>
        {(tc.station_pairs || []).map((pair, pi) => (
          <div class="pair-row2" key={pi}>
            <AcField value={pair[0]} ensure={fetchStations}
              placeholder="出发站 如 杭州东 / hzd" emptyText="无匹配车站(检查拼写)"
              onChange={(v) => setPair(pi, 0, v)} classExtra="grow2" />
            <span class="pair-arrow2">→</span>
            <AcField value={pair[1]} ensure={fetchStations}
              placeholder="到达站 如 重庆北 / cqb" emptyText="无匹配车站(检查拼写)"
              onChange={(v) => setPair(pi, 1, v)} classExtra="grow2" />
            <button class="btn danger sm" title="删除该车站对"
              onClick={() => setTC({
                station_pairs: tc.station_pairs.filter((_, i) => i !== pi) })}>×</button>
          </div>
        ))}
        <button class="btn sm"
          onClick={() => setTC({ station_pairs: (tc.station_pairs || []).concat([["", ""]]) })}>
          + 添加车站对
        </button>
      </div>
    </div>
  );
}

export default function RoutesView({ cfg, setCfg, cfgErr }) {
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  if (!cfg) return <div class="card"><div class="empty">{cfgErr || "加载中…"}</div></div>;
  const routes = cfg.routes || [];
  const update = (idx, patch) => setCfg(Object.assign({}, cfg, {
    routes: routes.map((r, i) => i === idx ? Object.assign({}, r, patch) : r),
  }));
  const doSave = () => {
    let payload;
    try {
      payload = cleanCfgForSave(cfg);
    } catch (e) {
      setMsg("保存失败: " + e.message);
      return;
    }
    setBusy(true); setMsg("保存中…");
    saveConfig(payload)
      .then((resp) => { setCfg(resp.config); setMsg("已保存 ✅ (查询类设置下次查询生效)"); })
      .catch((e) => setMsg("保存失败: " + (e.message || e)))
      .finally(() => setBusy(false));
  };
  return (
    <div>
      <div class="card">
        <div class="card-head">
          <h3>🧭 线路管理</h3>
          <span class="sub">城市/车站均为联想选择 · 保存后下次查询生效</span>
        </div>
        <div class="tpl-row2">
          <span class="f-label2">快捷添加:</span>
          {ROUTE_TPLS.map((tp) => (
            <button key={tp.from + tp.to} class="chiplet"
              onClick={() => setCfg(Object.assign({}, cfg, { routes: routes.concat([{
                id: "r" + Date.now().toString(36),
                from_city: tp.from, to_city: tp.to,
                window_days: 60, threshold_total: tp.th,
                trip_type: "oneway", intl: false,
                from_iata: "", to_iata: "",
                train_compare: { enabled: true,
                  station_pairs: tp.pairs.map((p) => p.slice()) },
              }]) }))}>{tp.from} ✈ {tp.to}</button>
          ))}
        </div>
        {routes.map((r, i) => (
          <RouteCard key={r.id || i} r={r} idx={i}
            update={(patch) => update(i, patch)}
            remove={() => setCfg(Object.assign({}, cfg, {
              routes: routes.filter((_, j) => j !== i) }))} />
        ))}
        {!routes.length ? (
          <div class="empty">暂无线路 · 点上方快捷模板添加第一条</div>
        ) : null}
        <div class="row-btns">
          <button class="btn primary" disabled={busy} onClick={doSave}>保存线路</button>
          {msg ? <span class="muted push-msg">{msg}</span> : null}
        </div>
      </div>
    </div>
  );
}
