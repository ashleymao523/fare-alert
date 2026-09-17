import { useEffect, useState } from "preact/hooks";
import { saveConfig, fetchCities, runNow } from "../lib/api.js";
import { filterAC } from "./AcField.jsx";
import CabinTimetable from "./CabinTimetable.jsx";

const fmt = (n) => (typeof n === "number" ? "¥" + Math.round(n) : "-");

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

// v0.45: watch-cities chips input - pick from the same curated city list
// as the route form (exact match, no fuzzy fallback); Enter adds free
// text too, Backspace on empty input removes the last chip.
function CityPicker({ cities, onChange }) {
  const [q, setQ] = useState("");
  const [list, setList] = useState(null);
  const [items, setItems] = useState([]);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  const refresh = (v) => {
    if (list == null) {
      fetchCities().then((x) => {
        setList(x);
        const f = filterAC(x, v);
        setItems(f);
        setActive(f.length ? 0 : -1);
      }).catch(() => {});
      setOpen(true);
      return;
    }
    const f = filterAC(list, v);
    setItems(f);
    setActive(f.length ? 0 : -1);
    setOpen(true);
  };
  const add = (name) => {
    const n = String(name || "").trim();
    if (!n) return;
    if (!cities.includes(n)) onChange(cities.concat([n]));
    setQ("");
    setOpen(false);
  };
  const onKey = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (open && active >= 0 && items[active]) add(items[active].name);
      else if (q.trim()) add(q);
    } else if (e.key === "Backspace" && !q && cities.length) {
      onChange(cities.slice(0, -1));
    } else if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "ArrowDown" && items.length) {
      e.preventDefault();
      setActive((active + 1) % items.length);
    } else if (e.key === "ArrowUp" && items.length) {
      e.preventDefault();
      setActive((active - 1 + items.length) % items.length);
    }
  };
  return (
    <div class="cw-chips">
      {cities.map((c) => (
        <span class="cw-chip" key={c}>{c}
          <button type="button" aria-label={"移除" + c}
            onClick={() => onChange(cities.filter((x) => x !== c))}>×</button>
        </span>
      ))}
      <div class="ac-wrap2 cw-ac">
        <input type="text" value={q} placeholder="输入城市, 回车或点选添加"
          role="combobox" aria-expanded={open}
          onFocus={() => refresh(q)}
          onInput={(e) => { setQ(e.target.value); refresh(e.target.value); }}
          onKeyDown={onKey}
          onBlur={() => setTimeout(() => setOpen(false), 150)} />
        {open ? (
          <div class="ac-list2" role="listbox">
            {list == null ? (
              <div class="ac-item2">加载中…</div>
            ) : items.length ? items.map((it, i) => (
              <div key={it.name} role="option" aria-selected={i === active}
                class={"ac-item2" + (i === active ? " active" : "")}
                onMouseDown={(e) => { e.preventDefault(); add(it.name); }}
                onMouseEnter={() => setActive(i)}>
                <span class="ac-label2">{it.name}</span>
                {it.pinyin ? <span class="ac-sub2">{it.pinyin}</span> : null}
              </div>
            )) : (
              <div class="ac-item2">无匹配, 回车直接添加</div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function CabinCard({ cfg, setCfg }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [runBusy, setRunBusy] = useState(false);
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
      toCities: (live.to_cities && live.to_cities.length
        ? live.to_cities
        : [live.default_to_city || cw.default_to_city || "杭州"]).slice(),
      threshold_total: live.threshold_total || cw.threshold_total || 1500,
      routeThresholds: Object.assign({},
        live.route_thresholds || cw.route_thresholds || {}),
      cooldown_hours:
        live.cooldown_hours != null ? live.cooldown_hours
          : (cw.cooldown_hours != null ? cw.cooldown_hours : 12),
      alertRecordLow: live.alert_record_low != null
        ? !!live.alert_record_low : true,
      cities: (live.watch_from_cities || []).slice(),
      intervalMinutes: ((data.refresh || {}).interval_minutes) || 45,
      patrolMinutes: ((data.patrol || {}).interval_minutes) || 30,
    });
  };
  const cancelEdit = () => { setEditing(false); setMsg(""); };
  const doRun = () => {
    setRunBusy(true);
    setMsg("手动刷新中…");
    runNow()
      .then(() => { load(); setMsg("刷新完成 ✅"); })
      .catch((e) => setMsg("刷新失败: " + (e.message || e)))
      .finally(() => setRunBusy(false));
  };
  const doSave = () => {
    const nextCw = {
      enabled: !!draft.enabled,
      cabins: (live.cabins && live.cabins.length) ? live.cabins : ["business"],
      to_cities: draft.toCities.slice(),
      default_to_city: draft.toCities[0] || "杭州",
      threshold_total: Number(draft.threshold_total) || 1500,
      route_thresholds: draft.routeThresholds || {},
      cooldown_hours: Number(draft.cooldown_hours) || 0,
      alert_record_low: !!draft.alertRecordLow,
      watch_from_cities: draft.cities.slice(),
      refresh_minutes: Math.max(5,
        Math.round(Number(draft.patrolMinutes) || 30)),
    };
    const next = Object.assign({}, cfg, { cabin_watch: nextCw });
    // v0.59: refresh cadence rides the global worker schedule; the cabin
    // form edits it in place (backend clamps to >= 5 minutes).
    next.schedule = Object.assign({}, (cfg && cfg.schedule) || {}, {
      interval_minutes: Math.max(5,
        Math.round(Number(draft.intervalMinutes) || 45)),
    });
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

  const destList = (cw.to_cities && cw.to_cities.length)
    ? cw.to_cities : [cw.default_to_city || "杭州"];
  const dests = destList.join(" / ");
  const rf = data.refresh || {};
  const pt = data.patrol || {};
  const hhmm = (ts) => ts
    ? new Date(ts * 1000).toLocaleTimeString("zh-CN",
        { hour: "2-digit", minute: "2-digit" }) : "-";
  const routes = (data.history && data.history.routes) || {};
  // v0.62: server-side leaderboard (all-time low WITH its fare date,
  // latest obs, gap-to-record); local derivation stays as a fallback
  // for snapshots served by an older backend.
  const rows = data.board || Object.entries(routes)
    .map(([id, r]) => ({
      route_id: id, from_city: r.from_city, to_city: r.to_city,
      low: r.lowest, low_date: "", latest: null, gap: null,
      samples: (r.obs || []).length,
    }))
    .sort((a, b) => (a.low || 1e9) - (b.low || 1e9));
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
              <span class="f-label2">心理价位 (总价)</span>
              <input type="number" min="1" value={draft.threshold_total}
                onInput={(e) => setD("threshold_total", e.target.value)} />
            </label>
            {(data.board || []).length ? (
              <div class="field2">
                <span class="f-label2">分线阈值（可选, 覆盖统一心理价位, 留空=用统一值）</span>
                <div class="push-grid">
                  {data.board.map((b) => {
                    const key = b.from_city + ">" + b.to_city;
                    return (
                      <label class="field2" key={key}>
                        <span class="f-label2">{b.from_city} → {b.to_city}</span>
                        <input type="number" min="0" placeholder="用统一阈值"
                          value={draft.routeThresholds[key] || ""}
                          onInput={(e) => setD("routeThresholds",
                            Object.assign({}, draft.routeThresholds,
                              { [key]: e.target.value }))} />
                      </label>
                    );
                  })}
                </div>
              </div>
            ) : null}
            <label class="field2">
              <span class="f-label2">提醒冷却 (小时)</span>
              <input type="number" min="0" value={draft.cooldown_hours}
                onInput={(e) => setD("cooldown_hours", e.target.value)} />
            </label>
            <label class="field2">
              <span class="f-label2">历史新低即提醒</span>
              <input type="checkbox" checked={!!draft.alertRecordLow}
                onChange={(e) => setD("alertRecordLow", e.target.checked)} />
            </label>
            <label class="field2">
              <span class="f-label2">刷新间隔 (分钟)</span>
              <input type="number" min="5" value={draft.intervalMinutes}
                onInput={(e) => setD("intervalMinutes", e.target.value)} />
            </label>
            <label class="field2">
              <span class="f-label2">独立巡检间隔 (分钟)</span>
              <input type="number" min="5" value={draft.patrolMinutes}
                onInput={(e) => setD("patrolMinutes", e.target.value)} />
            </label>
          </div>
          <div class="field2">
            <span class="f-label2">监控目的地（可多个, 默认杭州）</span>
            <CityPicker cities={draft.toCities}
              onChange={(cs) => setD("toCities", cs)} />
          </div>
          <div class="field2">
            <span class="f-label2">监控出发城市 (点选或回车添加, 留空 = 全部出发地)</span>
            <CityPicker cities={draft.cities}
              onChange={(cs) => setD("cities", cs)} />
          </div>
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
            目的地 {dests} · 阈值 {fmt(cw.threshold_total)} ·
            冷却 {(cw.cooldown_hours || 0) + "h"}
            {Object.keys(cw.route_thresholds || {}).length
              ? " · 分线 " + Object.entries(cw.route_thresholds)
                  .map(([k, v]) => k + " ¥" + Math.round(v)).join(" · ") : ""}
            {(cw.alert_record_low != null ? cw.alert_record_low : true)
              ? " · 新低即提醒" : ""}
            {(cw.watch_from_cities || []).length
              ? " · 出发地 " + cw.watch_from_cities.join("/") : ""}
          </div>
          <div class="cabin-refresh">
            <span class="badge gray">定时刷新</span>
            <span>每 {rf.interval_minutes || 45} 分钟一轮</span>
            {rf.last_cycle_ts
              ? <span>上轮 {hhmm(rf.last_cycle_ts)}</span> : null}
            {rf.next_cycle_ts
              ? <span>下轮 ≈{hhmm(rf.next_cycle_ts)}</span> : null}
            {cw.enabled && data.amadeus_ready === false ? (
              <span class="badge amber">公务舱数据源未配置</span>
            ) : null}
            {(pt.legs || []).length ? (
              <span class="cw-patrol" title={pt.last_status || ""}>
                独立巡检 每 {pt.interval_minutes || 30} 分钟
                {pt.last_run
                  ? " · 上轮 " + String(pt.last_run).slice(11, 16) : ""}
              </span>
            ) : null}
            <button class="btn sm" disabled={runBusy} onClick={doRun}>
              {runBusy ? "刷新中…" : "立即刷新"}
            </button>
          </div>
          {(data.qualifying_routes || []).length ? (
            <div class="cw-routes">
              <span class="muted">采集路线</span>
              {(data.qualifying_routes || []).map((r, i) => (
                <span class="cw-route" key={i}>
                  {r.from_city}→{r.to_city}
                  {r.mirror ? <span class="cw-mirror" title="由反向路线自动镜像采集">镜像</span> : null}
                </span>
              ))}
              {((data.patrol || {}).legs || []).map((r, i) => (
                <span class="cw-route" key={"p" + i}>
                  {r.from_city}→{r.to_city}
                  <span class="cw-mirror" title="独立巡检腿, 无需添加路线">巡检</span>
                </span>
              ))}
            </div>
          ) : (cw.enabled ? (
            <div class="cw-routes muted">
              暂无匹配路线——在「路线」页添加任意方向含 {dests} 的路线即可自动采集(支持反采)
            </div>
          ) : null)}
          {rows.length ? (
            <div>
              <div class="cabin-meta">🏆 历史低价榜 · 按历史最低排序</div>
              <table class="tbl">
                <thead>
                  <tr><th>出发</th><th>到达</th><th>历史最低</th><th>最新</th><th>走势</th><th>样本</th><th>状态</th></tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const obs = (routes[r.route_id] || {}).obs;
                    return (
                      <tr key={r.route_id}>
                        <td>{r.from_city}</td>
                        <td>{r.to_city}</td>
                        <td class="price">{fmt(r.low)}
                          {r.low_date
                            ? <span class="cw-date">{String(r.low_date).slice(5)}</span>
                            : null}
                          {obs && obs.length && obs[obs.length - 1].record
                            ? <span class="cw-mirror" title="最近一轮创下历史新低">新低</span>
                            : null}</td>
                        <td>{fmt(r.latest)}
                          {typeof r.gap === "number" && r.gap > 0
                            ? <span class="cw-date">距新低 +{fmt(r.gap)}</span>
                            : null}</td>
                        <td><Spark obs={obs} /></td>
                        <td>{r.samples}</td>
                        <td>
                          <span class={"badge " + (r.low <= (r.threshold || cw.threshold_total || 0) ? "green" : "gray")}>
                            {r.low <= (r.threshold || cw.threshold_total || 0) ? "低于阈值" : "观察中"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div class="empty">
              {cw.enabled
                ? "暂无公务舱样本 · 需配置 Amadeus 密钥后自动采集 (推送页可测)"
                : "点击右上「编辑」开启后, 各出发地飞 " + dests + " 的公务舱最低价会在此汇总"}
            </div>
          )}
          {data.last_alert ? (
            <div class="cabin-last">
              最近提醒: {data.last_alert.from_city}到{data.last_alert.to_city} ·
              {data.last_alert.date} · {fmt(data.last_alert.price)}
              {data.last_alert.kind === "record" ? " · 历史新低" : ""}
            </div>
          ) : null}
          <CabinTimetable timetable={data.timetable} />
          {msg && !editing ? <div class="muted push-msg">{msg}</div> : null}
        </div>
      )}
    </div>
  );
}
