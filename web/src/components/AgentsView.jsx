import { useEffect, useState } from "preact/hooks";
import { fetchTasks, runAgentPath } from "../lib/api.js";

const fmtAge = (m) => (m == null ? "-"
  : m < 60 ? Math.round(m) + " 分钟前"
  : m < 1440 ? (m / 60).toFixed(1) + " 小时前"
  : (m / 1440).toFixed(1) + " 天前");

const fmtCadence = (m) => (m < 60 ? m + " 分钟"
  : m < 1440 ? Math.round(m / 60) + " 小时"
  : Math.round(m / 1440) + " 天");

function StatusBadge({ s }) {
  if (s === "ok") return <span class="badge green">正常</span>;
  if (s === "late") return <span class="badge amber">滞后</span>;
  return <span class="badge gray">待首次运行</span>;
}

function AgentCard({ a, onRun }) {
  const [busy, setBusy] = useState(false);
  const fire = () => {
    setBusy(true);
    runAgentPath(a.id === "scan-all" ? "/api/run" : a.manual_trigger,
      a.id === "scan-all" ? { push: true } : {})
      .then(() => onRun())
      .catch(() => {})
      .finally(() => setBusy(false));
  };
  return (
    <div class={"agent-card" + (a.status === "late" ? " late"
      : a.status === "idle" ? " idle" : "")}>
      <div class="agent-head">
        <span class="agent-ico">{a.icon || "🤖"}</span>
        <span class="agent-name">{a.name || a.id}</span>
        <StatusBadge s={a.status} />
        {a.manual_trigger ? (
          <button class="btn sm" disabled={busy} onClick={fire}>
            {busy ? "执行中…" : a.id === "scan-all" ? "立即扫描" : "立即执行"}
          </button>
        ) : null}
      </div>
      {a.detail ? <div class="agent-detail">{a.detail}</div> : null}
      <div class="agent-meta">
        <span>上次 {a.last_run || "—"} ({fmtAge(a.age_min)})</span>
        <span>节奏 {fmtCadence(a.cadence_minutes || 0)}</span>
        <span>下次 {a.next_due || "—"}</span>
      </div>
    </div>
  );
}

export default function AgentsView() {
  const [doc, setDoc] = useState(null);
  const [err, setErr] = useState("");
  const load = () => fetchTasks()
    .then(setDoc)
    .catch((e) => setErr(String(e.message || e)));
  useEffect(() => { load(); }, []);
  const agents = (doc && doc.ledger && doc.ledger.agents) || [];
  return (
    <div class="card">
      <div class="card-head">
        <h3>🤖 任务中心</h3>
        <div class="head-actions">
          <button class="btn sm" onClick={load}>刷新</button>
        </div>
      </div>
      <div class="muted sub">
        7 个后台 agent 的统一账本——状态/节奏/上次与下次, 可手动点火。
      </div>
      {err ? <div class="empty">账本加载失败: {err}</div> : null}
      {!doc && !err ? <div class="empty">加载中…</div> : null}
      {doc && !agents.length ? (
        <div class="empty">账本为空: 首次运行后这里会出现全部后台 agent</div>
      ) : null}
      {agents.length ? (
        <div class="agents-grid">
          {agents.map((a) => (
            <AgentCard key={a.id} a={a} onRun={load} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
