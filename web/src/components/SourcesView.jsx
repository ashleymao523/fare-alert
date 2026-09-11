import { useEffect, useState } from "preact/hooks";
import { saveConfig, fetchSchedStats, fetchHealth } from "../lib/api.js";

const DOW_NAMES = ["一", "二", "三", "四", "五", "六", "日"]; // /api/sched-stats: 0=周一

function CovBar({ label, val, total, cls }) {
  if (!total) return null;
  return (
    <div class="tc-row">
      <span class="tc-k">{label}</span>
      <div class="tc-bar"><div class={"tc-fill " + cls} style={"width:" + Math.round((val / total) * 100) + "%"} /></div>
      <span class="tc-v">{val}</span>
    </div>
  );
}

// cfg/meta are lifted to App so unsaved edits survive tab switches (no cross-tab overwrite)
export default function SourcesView({ snap, cfg, setCfg, meta, setMeta, cfgErr }) {
  const [stats, setStats] = useState(null);
  const [hb, setHb] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetchSchedStats().then(setStats).catch(() => {});
    fetchHealth().then(setHb).catch(() => {});
  }, []);
  if (!cfg) return <div class="card"><div class="empty">{cfgErr || "加载中…"}</div></div>;
  const enabled = (cfg.sources && cfg.sources.enabled) || {};
  const ama = (cfg.sources && cfg.sources.amadeus) || {};
  const setSrc = (k, v) => setCfg(Object.assign({}, cfg, {
    sources: Object.assign({}, cfg.sources, {
      enabled: Object.assign({}, enabled, { [k]: v }),
    }),
  }));
  const setAma = (k, v) => setCfg(Object.assign({}, cfg, {
    sources: Object.assign({}, cfg.sources, {
      amadeus: Object.assign({}, ama, { [k]: v }),
    }),
  }));
  const doSave = () => {
    setBusy(true); setMsg("保存中…");
    saveConfig(cfg)
      .then((r) => { setCfg(r.config); setMeta(r.sources || meta); setMsg("已保存 ✅(下次查询生效)"); })
      .catch((e) => setMsg("保存失败: " + (e.message || e)))
      .finally(() => setBusy(false));
  };
  // aggregate time coverage across routes (strict scope, same as classic)
  let tot = 0, de = 0, db = 0, dm = 0, ae = 0, ab = 0, as = 0, am = 0;
  (((snap || {}).routes) || []).forEach((r) => {
    const c = r.time_coverage;
    if (!c) return;
    tot += c.total || 0;
    de += c.dep_exact || 0; db += c.dep_borrow || 0; dm += c.dep_missing || 0;
    ae += c.arr_exact || 0; ab += c.arr_borrow || 0; as += c.arr_est || 0; am += c.arr_missing || 0;
  });
  const dows = (stats && stats.dows) || {};
  const covered = Object.keys(dows).filter((k) => dows[k] > 0).length;
  const wk = hb && hb.worker;
  const alive = !!(wk && wk.ok && wk.age_min < 120);
  const hbState = !hb ? "未知" : alive ? "运行中" : wk ? "心跳过期" : "未启动";
  return (
    <div>
      <div class="card">
        <div class="card-head">
          <h3>⚙ 数据源开关</h3>
          <span class="sub">不可用源暂为规划中, 灰置</span>
        </div>
        {Object.keys(meta).map((k) => {
          const src = meta[k] || {};
          const ok = src.status === "可用";
          return (
            <div class="src-row2" key={k}>
              <input type="checkbox" checked={!!enabled[k]} disabled={!ok}
                onChange={(e) => setSrc(k, e.target.checked)} />
              <span class="s-name2">{src.name || k}</span>
              <span class={"chip2 " + (ok ? "ok" : "plan")}>{src.status || "规划"}</span>
              <span class="s-desc2">{src.desc || ""}</span>
            </div>
          );
        })}
        <div class="ama-box">
          <h4>Amadeus 国际源(可选 · 免费测试环境)</h4>
          <div class="push-grid">
            <label class="field2"><span class="f-label2">环境</span>
              <select value={ama.env === "prod" ? "prod" : "test"} onChange={(e) => setAma("env", e.target.value)}>
                <option value="test">test · 免费测试</option>
                <option value="prod">prod · 生产</option>
              </select>
            </label>
            <label class="field2"><span class="f-label2">client_id</span>
              <input type="text" value={ama.client_id || ""} onInput={(e) => setAma("client_id", e.target.value.trim())} />
            </label>
            <label class="field2"><span class="f-label2">client_secret</span>
              <input type="password" value={ama.client_secret || ""} onInput={(e) => setAma("client_secret", e.target.value)} />
            </label>
          </div>
          <div class="muted">配置后国际线获得真实起降时刻与缺价补全; 注册入口见经典版数据源页。</div>
        </div>
        <div class="row-btns">
          <button class="btn primary" disabled={busy} onClick={doSave}>保存配置</button>
          {msg ? <span class="muted push-msg">{msg}</span> : null}
        </div>
      </div>
      {hb ? (
      <div class="card">
        <div class="card-head">
          <h3>🫀 调度心跳</h3>
          <span class="sub">worker 每轮抓取后写入 /api/health</span>
        </div>
        <div class="hb-row">
          <span class={"hb-dot" + (alive ? " on" : "")}></span>
          <span class="hb-meta">
            <b>{hbState}</b>
            {wk ? <span> · 最近轮次 {wk.ok ? "成功" : "失败"} · {Math.round(wk.age_min)} 分钟前</span> : null}
          </span>
        </div>
        <div class="muted">
          {!wk ? "后台调度未启动: 可运行 tools/autostart_worker.ps1, 或重启后由自启项自动拉起。"
            : covered < 7 ? "时刻板按查询日沉淀, 约 " + (7 - covered) + " 天长满, 之后全部星期拥有精确起降时刻。"
            : "板库已长满, 换季时自动跟随新班期。"}
        </div>
      </div>
      ) : null}
      <div class="card">
        <div class="card-head">
          <h3>📅 时刻库沉淀进度</h3>
          <span class="sub">{stats && stats.flights ? stats.flights + " 个截班号已入库" : "首次查询后自动积累"}</span>
        </div>
        <div class="dow-row">
          {DOW_NAMES.map((w, i) => (
            <span class={"dow-chip" + (dows[String(i)] ? " has" : "")} key={i}>周{w}
              {dows[String(i)] ? <b>{dows[String(i)]}</b> : null}
            </span>
          ))}
        </div>
        <div class="muted">
          已覆盖 {covered}/7 个星期 · 板库按查询日自动沉淀, 约 7 天长满
 未覆盖星期的航班时刻以「跨日参考」展示。{covered >= 7 ? " ✅ 已长满" : ""}
        </div>
      </div>
      <div class="card">
        <div class="card-head">
          <h3>🩺 本轮时刻覆盖体检</h3>
          <span class="sub">真实可购航班口径(剔除参考/插值)</span>
        </div>
        {tot ? (
          <div>
            <CovBar label="起飞 · 精确" val={de} total={tot} cls="ok" />
            <CovBar label="起飞 · 跨日参考" val={db} total={tot} cls="mid" />
            <CovBar label="起飞 · 缺失" val={dm} total={tot} cls="miss" />
            <CovBar label="落地 · 精确" val={ae} total={tot} cls="ok" />
            <CovBar label="落地 · 跨日借用" val={ab} total={tot} cls="mid2" />
            <CovBar label="落地 · 估算" val={as} total={tot} cls="mid" />
            <CovBar label="落地 · 缺失" val={am} total={tot} cls="miss" />
            <div class="muted">共 {tot} 条 · 估算与参考仅作标注, 不触发低价提醒。</div>
          </div>
        ) : <div class="muted">跑一次查询后展示起飞/落地时刻来源构成。</div>}
      </div>
    </div>
  );
}
