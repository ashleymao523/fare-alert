import { useEffect, useState } from "preact/hooks";
import { fetchCrawl } from "../lib/api.js";

const SRC_NAMES = {
  "qunar-calendar": "去哪儿 · 低价日历",
  "qunar-intl": "去哪儿 · 国际特价",
  "12306-train": "12306 火车票查询",
  "amadeus-intl": "Amadeus · 国际低价",
  "amadeus-fill": "Amadeus · 缺价补全",
  "amadeus-times": "Amadeus · 时刻增强",
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
      {runs.length
        ? runs.map(({ run, live, rk }) => <RunCard run={run} live={live} key={rk} />)
        : <div class="card"><div class="empty">暂无抓取记录: 点面板「立即查询」或等计划任务触发</div></div>}
    </div>
  );
}
