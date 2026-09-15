import { useEffect, useState } from "preact/hooks";
import { fetchCrawl, fetchSnapshot, fetchHealth,
  fetchPointGaps, postPointFill, fetchBookmarklet } from "../lib/api.js";

const SRC_NAMES = {
  "qunar-calendar": "去哪儿 · 低价日历",
  "qunar-intl": "去哪儿 · 国际特价",
  "12306-train": "12306 火车票查询",
  "amadeus-intl": "Amadeus · 国际低价",
  "amadeus-fill": "Amadeus · 缺价补全",
  "amadeus-times": "Amadeus · 时刻增强",
  "point-fill": "精点核价 · 实抓",
  "hgh-board-times": "机场板期 · 参考时刻",
  "nearby-ref": "临近日参考价",
  interp: "插值估算价",
  push: "提醒推送",
};

// backend step enum: ok | skip | error | disabled (fail/err kept as legacy)
const ST_CLS = { ok: "ok", skip: "skip", error: "err", disabled: "skip", fail: "err", err: "err" };
const ST_TXT = { ok: "成功", skip: "跳过", error: "失败", disabled: "禁用", fail: "失败", err: "异常" };

function HealthRow({ s }) {
  const bad = s.degraded || (s.consecutive_fails || 0) > 0;
  const cands = ((s.diagnose || {}).candidates) || [];
  const errAt = s.last_error_at ? " · " + String(s.last_error_at).replace("T", " ").slice(5, 16) : "";
  return (
    <div class="hl-row">
      <span class={"hl-dot " + (bad ? "bad" : "good")} />
      <span class="hl-name">{SRC_NAMES[s.source] || s.source}</span>
      <span class="hl-meta">
        {s.score == null ? "-- 分" : s.score + " 分"}
        {s.last_ok_at ? " · 最近成功 " + String(s.last_ok_at).replace("T", " ") : ""}
      </span>
      {cands.map((c) => (
        <span class="hl-diag" key={c.cause} title={(c.action || "") + (s.last_error ? "\n错误: " + s.last_error : "")}>{c.cause}{errAt}</span>
      ))}
    </div>
  );
}

function StepRow({ st }) {
  return (
    <div class="step-row" title={st.error || ""}>
      <span class={"st-badge " + (ST_CLS[st.status] || "skip")}>{ST_TXT[st.status] || st.status}</span>
      <span class="st-src">{SRC_NAMES[st.source] || st.source}</span>
      <span class="st-label">{st.label}</span>
      <span class="st-action">{st.action}</span>
      {st.cached ? <span class="st-cached">缓存</span> : null}
      <span class="st-ms">{st.ms}ms</span>
      {st.count ? <span class="st-count">{st.count}条</span> : null}
      {st.error ? <span class="st-err">{st.error}</span> : null}
    </div>
  );
}

function RunCard({ run, live }) {
  const steps = run.steps || [];
  const nOk = steps.filter((x) => x.status === "ok").length;
  const nSkip = steps.filter((x) => x.status === "skip" || x.status === "disabled").length;
  const nErr = steps.filter((x) => x.status === "error" || x.status === "fail" || x.status === "err").length;
  const totalMs = steps.reduce((a, x) => a + (x.ms || 0), 0);
  return (
    <div class="card run-card">
      <div class="run-head">
        <h4>
          {live ? <span class="run-live" /> : null}
          {run.trigger === "manual" ? "手动" : run.trigger === "cli" ? "计划任务" : run.trigger || "抓取"}
          {" · " + String(run.started_at || "").replace("T", " ")}
        </h4>
        <span class="run-stats">
          {nOk} 成功 · {nSkip} 跳过 · {nErr} 失败 · {(totalMs / 1000).toFixed(1)}s
        </span>
      </div>
      {steps.map((st, i) => <StepRow st={st} key={i} />)}
    </div>
  );
}

// v0.78: qunar per-date point-search deep link (same shape as DayDetail).
function qunarPointUrl(from, to, date) {
  return "https://m.flight.qunar.com/ncs/page/flightlist?depCity="
    + encodeURIComponent(from) + "&arrCity=" + encodeURIComponent(to)
    + "&goDate=" + date + "&from=touch_index_search";
}

/* v0.78 point-fill UI: aggregated-calendar gap dates are often NOT sold
 * out - the OTA gateway just has no cached floor price yet (recon in
 * core/point_fill.py). One precise per-date query in a real browser
 * usually returns live prices; this card lists gap dates per route and
 * posts the captured pay price into the v0.76 point-fill cache. */
function PointFillCard() {
  const [gaps, setGaps] = useState(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState(null);
  const [total, setTotal] = useState("");
  const [fno, setFno] = useState("");
  const [dep, setDep] = useState("");
  const [arr, setArr] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [bm, setBm] = useState("");
  const [bmMsg, setBmMsg] = useState("");
  const load = () => fetchPointGaps()
    .then((d) => { setGaps(d.routes || []); setErr(""); })
    .catch((e) => setErr(String(e.message || e)));
  // v0.82: bookmarklet posts are fire-and-forget (no-cors), so the
  // panel cannot be notified - it re-polls the gap list instead.
  useEffect(() => {
    load();
    const iv = setInterval(load, 20000);
    return () => clearInterval(iv);
  }, []);
  const pick = (rt, date) => {
    setSel({ id: rt.id, from: rt.from_city, to: rt.to_city, date });
    setTotal(""); setFno(""); setDep(""); setArr(""); setMsg("");
  };
  const submit = () => {
    const v = parseFloat(total);
    if (!sel || !(v > 0)) { setMsg("请填最终付款价(数字)"); return; }
    setBusy(true); setMsg("提交中…");
    postPointFill({ route_id: sel.id, rows: [{
      date: sel.date, total: v,
      flight_no: fno.trim() || undefined,
      dep_time: dep.trim() || undefined,
      arr_time: arr.trim() || undefined,
    }] })
      .then((r) => {
        setMsg("已入库 " + (r.stored || 0) + " 条, 快照已热更新 ✅");
        setSel(null); load();
      })
      .catch((e) => setMsg("失败: " + (e.message || e)))
      .finally(() => setBusy(false));
  };
  const genBm = () => {
    setBmMsg("生成中…");
    fetchBookmarklet()
      .then((d) => { setBm(d.code || ""); setBmMsg(""); })
      .catch((e) => setBmMsg("失败: " + (e.message || e)));
  };
  const copyBm = () => {
    navigator.clipboard.writeText(bm)
      .then(() => setBmMsg("已复制 ✅ 去收藏栏「新建书签」把它粘为网址"))
      .catch(() => setBmMsg("复制失败: 手动全选下方代码复制"));
  };
  return (
    <div class="card">
      <div class="card-head">
        <h3>🎯 精点补查 · 缺价日期回填</h3>
        <span class="sub">聚合日历未出价 ≠ 售罄 · 点日期直达精查, 再点书签自动回填</span>
      </div>
      {err ? <div class="muted">加载失败: {err}</div> : null}
      {gaps === null ? <div class="muted">加载中…</div>
        : !gaps.length
          ? <div class="muted">✅ 各路线当前无缺价日期, 或已全部回填。</div>
          : gaps.map((rt) => (
            <div class="gap-route" key={rt.id}>
              <div class="gap-rt">
                <b>{rt.from_city} → {rt.to_city}</b>
                {rt.intl ? <span class="muted">国际</span> : null}
                <span class="muted">{(rt.gaps || []).length} 个缺价日</span>
              </div>
              <div class="gap-dates">
                {(rt.gaps || []).map((g) => (g.cached ? (
                  <span key={g.date} class="gap-chip cached"
                    title="已回填(48h 内有效), 到期或聚合源出价后自动让位">
                    {g.date.slice(5)} ✓
                  </span>
                ) : (
                  <a key={g.date}
                    class={"gap-chip link"
                      + (sel && sel.id === rt.id && sel.date === g.date ? " sel" : "")}
                    title="打开去哪儿单日精查 → 列表出来后点书签自动回填"
                    target="_blank" rel="noopener noreferrer"
                    href={qunarPointUrl(rt.from_city, rt.to_city, g.date)}
                    onClick={() => pick(rt, g.date)}>
                    {g.date.slice(5)} ↗
                  </a>
                )))}
              </div>
            </div>
          ))}
      {sel ? (
        <div class="pf-box">
          <div class="pf-head">
            回填 <b>{sel.from} → {sel.to} · {sel.date}</b>
            <a class="pf-link" target="_blank" rel="noopener noreferrer"
              href={qunarPointUrl(sel.from, sel.to, sel.date)}>
              先去单日精点查询 ↗</a>
          </div>
          <div class="push-grid">
            <label class="field2"><span class="f-label2">最终付款价 ¥ · 含税必填</span>
              <input type="number" min="1" step="0.1" placeholder="如 480"
                value={total} onInput={(e) => setTotal(e.target.value)} />
            </label>
            <label class="field2"><span class="f-label2">航班号 · 选填</span>
              <input type="text" placeholder="如 GJ5401" maxlength="8"
                value={fno} onInput={(e) => setFno(e.target.value)} />
            </label>
            <label class="field2"><span class="f-label2">起飞时刻 · 选填</span>
              <input type="text" placeholder="07:45" maxlength="5"
                value={dep} onInput={(e) => setDep(e.target.value)} />
            </label>
            <label class="field2"><span class="f-label2">落地时刻 · 选填</span>
              <input type="text" placeholder="10:30" maxlength="5"
                value={arr} onInput={(e) => setArr(e.target.value)} />
            </label>
          </div>
          <div class="row-btns">
            <button class="btn primary" disabled={busy} onClick={submit}>
              回填并热更新</button>
            <button class="btn" disabled={busy} onClick={() => setSel(null)}>取消</button>
            {msg ? <span class="muted push-msg">{msg}</span> : null}
          </div>
        </div>
      ) : null}
      <div class="bm-box">
        <div class="bm-head">
          <b>半自动 · 精点回填书签</b>
          <button class="btn" onClick={genBm}>{bm ? "重新生成" : "生成书签脚本"}</button>
          {bm ? <button class="btn primary" onClick={copyBm}>复制</button> : null}
          {bmMsg ? <span class="muted push-msg">{bmMsg}</span> : null}
        </div>
        <div class="muted">
          ① 在本面板(手机用局域网地址打开)点生成+复制 → ② 浏览器收藏栏「新建书签」
          把代码粘为网址 → ③ 在去哪儿精查页点这本书签, 自动抓最低价回填,
          抓不到会弹窗让你手输。脚本自动指向当前面板地址, 换设备重新生成即可。
        </div>
        {bm ? <textarea class="bm-code" readonly rows="4"
          onFocus={(e) => e.target.select()} value={bm} /> : null}
      </div>
      <div class="muted">
        口径: 填「选中乘机人后的最终付款价」, 系统自动扣除机建+燃油得裸价;
        回填缓存 48 小时, 期间若聚合源出价则以真实源优先。
      </div>
    </div>
  );
}

/* v0.78 per-route time sedimentation: exact vs borrowed dep-time share
 * per route + the dow board fill-up forecast. A board run on day D seeds
 * dow(D) AND dow(D+1) (core/sched_board.py), so every missing weekday
 * has a predictable auto-fill date. */
function nextRunForDow(target, now) {
  for (let i = 0; i < 7; i++) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i);
    const dow = (d.getDay() + 6) % 7; // 0 = Monday, python-aligned
    if (dow === target) return { date: d, via: "当日" };
    if ((dow + 1) % 7 === target) return { date: d, via: "次日沉淀" };
  }
  return null;
}

function TimeSedimentCard() {
  const [snap, setSnap] = useState(null);
  const [hb, setHb] = useState(null);
  useEffect(() => {
    fetchSnapshot().then(setSnap).catch(() => {});
    fetchHealth().then(setHb).catch(() => {});
  }, []);
  const routes = (((snap || {}).routes) || [])
    .filter((r) => r.time_coverage && r.time_coverage.total);
  const dows = (((hb || {}).board) || {}).dows || {};
  const miss = [];
  for (let i = 0; i < 7; i++) {
    if (!dows[String(i)] && !dows[i]) miss.push(i);
  }
  const now = new Date();
  const DOW = ["一", "二", "三", "四", "五", "六", "日"];
  const fmt = (d) => (d.getMonth() + 1) + "/" + d.getDate();
  return (
    <div class="card">
      <div class="card-head">
        <h3>⏱ 时刻沉淀 · 按路线透明度</h3>
        <span class="sub">起飞时刻: 精确(当日板) vs 跨日参考(借班期)</span>
      </div>
      {routes.length ? routes.map((r) => {
        const c = r.time_coverage;
        const pe = Math.round((c.dep_exact / c.total) * 100);
        const pb = Math.round((c.dep_borrow / c.total) * 100);
        return (
          <div class="tc-row" key={r.id}>
            <span class="tc-k">{r.from_city} → {r.to_city}</span>
            <div class="sed-bar">
              <div class="tc-fill ok" style={"width:" + pe + "%"} />
              <div class="tc-fill mid" style={"width:" + pb + "%"} />
            </div>
            <span class="tc-v" title={"精确 " + c.dep_exact + " · 借用 "
              + c.dep_borrow + " · 缺失 " + c.dep_missing}>{pe}%</span>
          </div>
        );
      }) : <div class="muted">跑一次查询后展示各路线起飞时刻来源构成。</div>}
      <div class="dow-row sed-dows">
        {DOW.map((w, i) => (
          <span class={"dow-chip" + (dows[String(i)] ? " has" : "")} key={i}>周{w}
            {dows[String(i)] ? <b>{dows[String(i)]}</b> : null}
          </span>
        ))}
      </div>
      <div class="muted">
        {miss.length
          ? "缺口自动补齐预测: " + miss.map((i) => {
              const n = nextRunForDow(i, now);
              return "周" + DOW[i] + " → " + (n ? fmt(n.date) + " 轮(" + n.via + ")" : "待排班");
            }).join(" · ") + " · 借用时刻在日详情中已打「借周X」标"
          : "✅ 七个星期全部长满, 所有班期拥有当日板精确时刻。"}
      </div>
    </div>
  );
}

export default function CrawlView() {
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    let alive = true;
    const tick = () => fetchCrawl()
      .then((d) => { if (alive) { setDoc(d); setErr(""); } })
      .catch((e) => { if (alive) setErr(String(e.message || e)); });
    tick();
    const t = setInterval(tick, 2000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  if (!doc) {
    return <div class="card"><div class="empty">{err ? "抓取状态加载失败: " + err : "加载中…"}</div></div>;
  }
  const runs = [];
  if (doc.current) runs.push({ run: doc.current, live: !!doc.running, rk: "current" });
  (doc.history || []).slice(0, 6).forEach((r, i) => runs.push({ run: r, live: false, rk: (r.run_id || r.started_at || "h") + "-" + i }));
  const srcs = ((doc.health || {}).sources) || [];
  return (
    <div>
      <div class="card">
        <div class="card-head">
          <h3>🕷 数据源健康</h3>
          <span class="sub">
            近 12 轮成功率 · 异常自动诊断
            {err ? <span class="poll-err"> · 轮询中断: {err}</span> : null}
          </span>
        </div>
        {srcs.map((s) => <HealthRow s={s} key={s.source} />)}
        {!srcs.length ? <div class="muted">暂无健康数据, 跑一次查询后出现</div> : null}
      </div>
      <PointFillCard />
      <TimeSedimentCard />
      {runs.length
        ? runs.map(({ run, live, rk }) => <RunCard run={run} live={live} key={rk} />)
        : <div class="card"><div class="empty">暂无抓取记录: 点面板「立即查询」或等计划任务触发</div></div>}
    </div>
  );
}
