import { useEffect, useState } from "preact/hooks";
import { fetchWeekly, pushWeekly } from "../lib/api.js";
import { fmtMoney } from "../lib/data.js";

function Spark({ series }) {
  // series items are [date, price] pairs from /api/weekly-report
  const pts = (series || []).map((p) => (p && p[1]) || 0).filter((v) => v > 0);
  if (pts.length < 2) return <div class="wk2-nodata">数据不足, 每天归档后自动成图</div>;
  const min = Math.min.apply(null, pts);
  const max = Math.max.apply(null, pts);
  const span = max - min || 1;
  const W = 220, H = 40;
  const path = pts.map((v, i) => {
    const x = (i / (pts.length - 1)) * W;
    const y = H - 4 - ((v - min) / span) * (H - 8);
    return x.toFixed(1) + "," + y.toFixed(1);
  }).join(" ");
  return (
    <svg class="wk2-spark" viewBox={"0 0 " + W + " " + H} preserveAspectRatio="none">
      <polyline points={path} class="wk2-line" />
    </svg>
  );
}

export default function WeeklyView() {
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  const [pushMsg, setPushMsg] = useState("");
  const [pushing, setPushing] = useState(false);
  const [showPush, setShowPush] = useState(false);
  const load = () => fetchWeekly()
    .then((r) => { setRep(r); setErr(""); })
    .catch((e) => setErr(String(e.message || e)));
  useEffect(() => { load(); }, []);
  if (err && !rep) return <div class="card"><div class="empty">周报加载失败: {err}</div></div>;
  if (!rep) return <div class="card"><div class="empty">加载中…</div></div>;
  const hasCh = !!rep.channel_ready;
  const hl = rep.highlights || null;
  const doPush = () => {
    setPushing(true); setPushMsg("");
    pushWeekly()
      .then((r) => setPushMsg("已推送 ✅ " + (r.results || []).join(" · ")))
      .catch((e) => setPushMsg("推送失败 " + (e.message || e)))
      .finally(() => setPushing(false));
  };
  return (
    <div>
      <div class="card">
        <div class="card-head">
          <h3>📊 洞察周报</h3>
          <span class="sub">每日指标自动归档 · 每个数字可从历史重算</span>
        </div>
        {!hasCh ? (
          <div class="warn-box">
            ⚠️ 周报推送尚未就绪: 先到「推送」页填写 Bark Key(iPhone) 或 ServerChan
            SendKey(微信), 保存后回到此页点「立即推送」验证送达。
          </div>
        ) : null}
        <div class="wk2-text">{rep.text || ""}</div>
        <div class="row-btns">
          <button class="btn" onClick={load}>刷新</button>
          <button class="btn" onClick={() => setShowPush(!showPush)}>
            {showPush ? "收起推送预览" : "预览推送正文"}
          </button>
          <button class="btn primary" disabled={!hasCh || pushing} onClick={doPush}
            title={hasCh ? "" : "请先在「推送」页配置 Bark 或 ServerChan"}>
            {pushing ? "推送中…" : "立即推送周报"}
          </button>
          {pushMsg ? <span class="muted push-msg">{pushMsg}</span> : null}
        </div>
        {showPush ? (
          <div class="wk2-push-prev">
            <div class="wk2-push-cap">📱 手机实际收到的推送正文</div>
            <div class="wk2-text">{rep.push_text || rep.text || ""}</div>
          </div>
        ) : null}
      </div>
      {hl ? (
        <div class="card wk2-card">
          <div class="card-head">
            <h4>⭐ 本周值得关注</h4>
            <span class="sub">最大降幅 · 破线路线 · 双闸骤降，一屏速览</span>
          </div>
          <div class="wk2-hl">
            {hl.biggest_drop ? (
              <div class="wk2-hl-row">
                <span class="chip2 hero">最大降幅</span>
                <b>{hl.biggest_drop.name}</b>
                <span class="wk2-hl-nums">
                  {fmtMoney(hl.biggest_drop.prev_min)} → {fmtMoney(hl.biggest_drop.week_min)}
                </span>
                <span class="chip2 ok">
                  -¥{Math.round(Math.abs(hl.biggest_drop.delta))}（{Math.round(Math.abs(hl.biggest_drop.pct))}%）
                </span>
              </div>
            ) : null}
            {(hl.below_threshold || []).map((b, i) => (
              <div class="wk2-hl-row" key={"below-" + i}>
                <span class="chip2 hero">低于阈值</span>
                <b>{b.name}</b>
                <span class="wk2-hl-nums">窗口内 {b.days_below} 天 ≤ {fmtMoney(b.threshold)} · 最低 {fmtMoney(b.cheapest_total)}</span>
              </div>
            ))}
            {(hl.sharp_drops || []).map((s, i) => (
              <div class="wk2-hl-row" key={"sharp-" + i}>
                <span class="chip2 ok">骤降</span>
                <b>{s.name}</b>
                <span class="wk2-hl-nums">{(s.date || "").slice(5)} {fmtMoney(s.prev)} → {fmtMoney(s.today)}</span>
                <span class="chip2">-{Math.round(Math.abs(s.pct))}% / -¥{Math.round(Math.abs(s.delta))}</span>
              </div>
            ))}
          </div>
          <div class="muted wk2-hl-note">{hl.text}</div>
        </div>
      ) : null}
      {(rep.routes || []).map((r) => (
        <div class="card wk2-card" key={r.id || r.name}>
          <div class="wk2-head">
            <h4>{r.name}</h4>
            <div class="wk2-chips">
              <span class="chip2 hero">本周最低 {fmtMoney(r.week.min)}</span>
              <span class="chip2">本周均价 {fmtMoney(r.week.avg)}</span>
              <span class="chip2">{r.prev ? "上周最低 " + fmtMoney(r.prev.min) : "上周暂无数据"}</span>
            </div>
          </div>
          <div class="wk2-body">
            <Spark series={r.series} />
            <div class="wk2-info">{r.text}</div>
          </div>
        </div>
      ))}
      {!rep.ok ? (
        <div class="card"><div class="muted">暂无历史数据: 跑一次查询后每天自动归档指标; 累积 8 天起周报带环比。</div></div>
      ) : null}
    </div>
  );
}
