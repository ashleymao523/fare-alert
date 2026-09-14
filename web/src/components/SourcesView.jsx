import { useEffect, useState } from "preact/hooks";
import { saveConfig, fetchSchedStats, fetchHealth, fetchAmaUsage,
  fetchCovTrend, searchBoard } from "../lib/api.js";

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

// v0.54: search the zero-key schedule library (city pair / flight no) -
// shows what actually flies each weekday, i.e. the engine behind
// alt-ref reference times, and a planning tool in its own right.
function BoardExplorer() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [rows, setRows] = useState(null);
  const [busy, setBusy] = useState(false);
  const go = () => {
    setBusy(true);
    searchBoard({ from: from.trim(), to: to.trim(), limit: 30 })
      .then((r) => setRows(r.flights || []))
      .catch(() => setRows([]))
      .finally(() => setBusy(false));
  };
  return (
    <div class="board-explorer">
      <div class="push-grid">
        <label class="field2"><span class="f-label2">出发城市</span>
          <input type="text" placeholder="如 杭州, 留空查全部" value={from}
            onInput={(e) => setFrom(e.target.value)} />
        </label>
        <label class="field2"><span class="f-label2">到达城市</span>
          <input type="text" placeholder="如 重庆, 留空查全部" value={to}
            onInput={(e) => setTo(e.target.value)} />
        </label>
      </div>
      <div class="row-btns">
        <button class="btn" disabled={busy} onClick={go}>
          {busy ? "查询中…" : "班期查询"}
        </button>
        {rows ? <span class="muted">命中 {rows.length} 班(按起飞时间排序)</span> : null}
      </div>
      {rows && rows.length ? (
        <div class="tbl-scroll">
          <table class="tbl">
            <thead>
              <tr><th>航班</th><th>航司 / 机型</th><th>航线</th><th>起飞→到达</th><th>班期</th></tr>
            </thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.no}>
                  <td class="num">{f.no}</td>
                  <td>{f.airline}{f.craft ? " · " + f.craft : ""}</td>
                  <td>{f.from} → {f.to}</td>
                  <td class="num">{f.dep} → {f.arr}</td>
                  <td>
                    <span class="dow-mini-row">
                      {DOW_NAMES.map((w, i) => (
                        <span class={"dow-mini" + (f.dows.indexOf(i) >= 0 ? " has" : "")}
                          key={i}>{w}</span>
                      ))}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : rows ? <div class="muted">库中暂无匹配班次; 随每日抓取自动沉淀。</div> : (
        <div class="muted">查任意城市对的已沉淀计划班次(航班号/起降时刻/班期), 留空查全部。</div>
      )}
    </div>
  );
}

// v0.45: dep-time exactness over archived days (flat fill, no gradient
// tricks) - shows whether goal-1 coverage is actually growing.
function CovTrend({ pts }) {
  if (pts && pts.length === 1) {
    return (
      <div class="cvt-sub cov-trend">
        趋势基线已记录（今日起飞精确 {pts[0].pct}%），
        明日起绘制覆盖率曲线。
      </div>
    );
  }
  if (!pts || pts.length < 2) return null;
  const W = 320, H = 72, PL = 8, PR = 34, PT = 8, PB = 14;
  const x = (i) => PL + (i * (W - PL - PR)) / (pts.length - 1);
  const y = (p) => PT + ((100 - p) / 100) * (H - PT - PB);
  const line = pts.map((p, i) => (i ? "L" : "M") + x(i).toFixed(1)
    + " " + y(p.pct).toFixed(1)).join(" ");
  const area = line + " L" + x(pts.length - 1).toFixed(1) + " " + (H - PB)
    + " L" + PL + " " + (H - PB) + " Z";
  const last = pts[pts.length - 1];
  return (
    <div class="cov-trend">
      <svg class="cvt-svg" viewBox={"0 0 " + W + " " + H} role="img"
        aria-label="起飞时刻精确占比趋势">
        <line class="cvt-guide" x1={PL} y1={y(100)} x2={W - PR} y2={y(100)} />
        <line class="cvt-guide" x1={PL} y1={y(50)} x2={W - PR} y2={y(50)} />
        <path class="cvt-area" d={area} />
        <path class="cvt-line" d={line} />
        {pts.map((p, i) => (
          <circle key={p.date}
            class={"cvt-dot" + (i === pts.length - 1 ? " cvt-last" : "")}
            cx={x(i)} cy={y(p.pct)} r={i === pts.length - 1 ? 3 : 2} />
        ))}
        <text class="cvt-cap" x={W - PR + 4} y={y(last.pct) + 3}>
          {Math.round(last.pct)}%
        </text>
        <text class="cvt-cap" x={PL} y={H - 3}>{pts[0].date.slice(5)}</text>
        <text class="cvt-cap" x={W - PR} y={H - 3} text-anchor="end">
          {last.date.slice(5)}
        </text>
      </svg>
      <div class="cvt-sub">
        近{pts.length}天 起飞精确占比 {pts[0].pct}% → {last.pct}%
        <span> · 跨日参考 {Math.round(last.db * 100 / last.tot)}%</span>
        <span> · 缺失 {Math.round(last.dm * 100 / last.tot)}%</span>
      </div>
    </div>
  );
}

// cfg/meta are lifted to App so unsaved edits survive tab switches (no cross-tab overwrite)
export default function SourcesView({ snap, cfg, setCfg, meta, setMeta, cfgErr }) {
  const [stats, setStats] = useState(null);
  const [usage, setUsage] = useState(null);
  const [covT, setCovT] = useState(null);
  const [hb, setHb] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    fetchSchedStats().then(setStats).catch(() => {});
    fetchHealth().then(setHb).catch(() => {});
    fetchAmaUsage().then(setUsage).catch(() => {});
    fetchCovTrend().then((x) => setCovT(x.trend || [])).catch(() => {});
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
  const pt = (hb && hb.revive && hb.revive.supervisor
    && hb.revive.supervisor.patrol) || null;
  // v0.51: worker runs older code than the webui -> amber banner; the
  // supervisor hot-swaps it within one 5-min pass (or restart_all.ps1).
  const sr = (hb && hb.revive && hb.revive.supervisor
    && hb.revive.supervisor.last_stale_restart) || null;
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
          {(usage && usage.today != null) ? (
            <div class="muted">Amadeus 今日调用 {usage.today} 次(14 天滚动计数, 含缓存命中前的真实请求)。</div>
          ) : null}
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
        {(wk && wk.code_synced === false) ? (
          <div class="warn-box">
            ⚠ Worker 代码落后（心跳 v{wk.code_ver || "旧版"}）：守护线程将自动热替换为最新代码，或运行 tools/restart_all.ps1 立即生效。
          </div>
        ) : null}
        <div class="muted">
          {!wk ? ((hb.revive && ((hb.revive.supervisor && hb.revive.supervisor.enabled)
              || (hb.revive.task && hb.revive.task.installed)))
              ? "后台调度未启动: 每日自愈机制将在明早 07:00 后自动拉起, 无需手动干预。"
              : "后台调度未启动: 可运行 tools/autostart_worker.ps1, 或重启后由自启项自动拉起。")
            : covered < 7 ? "时刻板按查询日沉淀, 约 " + (7 - covered) + " 天长满, 之后全部星期拥有精确起降时刻。"
            : "板库已长满, 换季时自动跟随新班期。"}
        </div>
        {hb.revive ? (
          <div class="muted">
            🛟 每日自愈: {(hb.revive.supervisor && hb.revive.supervisor.enabled)
              ? "面板守护已启用, 每日 07:00 后自动拉活后台抓取"
              : "面板守护未启用(config deploy.supervise_worker)"}
            {(hb.revive.task && hb.revive.task.installed) ? " · 计划任务已装" : ""}
            {(sr && sr.ts) ? " · 已自动热替换 " + (sr.from || "?") + "→" + (sr.to || "?") : ""}
          </div>
        ) : null}
        {pt ? (
          <div class="muted">
            🔎 每日巡检: {pt.enabled
              ? "已启用, 每日 09:00 后自动体检, 异常时经配置渠道提醒"
              : "未启用(config deploy.patrol_daily)"}
            {(pt.last && pt.last.verdict)
              ? " · 最近结论: " + pt.last.verdict : ""}
            {pt.last_error ? " · 最近异常: " + pt.last_error : ""}
            {(pt.last && pt.last.time_fill && pt.last.time_fill.dep_total)
              ? " · 时刻回写: 起飞 " + pt.last.time_fill.dep_covered + "/"
                + pt.last.time_fill.dep_total + " (巡检后离线补全)"
              : ""}
          </div>
        ) : null}
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
        <BoardExplorer />
      </div>
      <div class="card">
        <div class="card-head">
          <h3>🩺 本轮时刻覆盖体检</h3>
          <span class="sub">真实可购航班口径(剔除参考/插值)</span>
        </div>
        {tot ? (
          <div>
            <CovTrend pts={covT} />
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
