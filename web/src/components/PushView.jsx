import { useEffect, useState } from "preact/hooks";
import { saveConfig, testPush, fetchAlerts, fetchWeekly, fetchLanInfo,
  fetchDrops } from "../lib/api.js";

function Field({ label, children }) {
  return <label class="field2"><span class="f-label2">{label}</span>{children}</label>;
}

function fmtTs(s) {
  return s ? String(s).replace("T", " ").slice(0, 16) : "";
}

function LanCard() {
  const [lan, setLan] = useState(null);
  useEffect(() => { fetchLanInfo().then(setLan).catch(() => {}); }, []);
  if (!lan) return null;
  return (
    <div class="card">
      <div class="card-head">
        <h3>📱 手机访问</h3>
        <span class="sub">同一 Wi-Fi 下 iPhone / 其他设备直接打开</span>
      </div>
      <div class="push-status">
        <span class={"chip2 " + (lan.lan_open ? "ok" : "plan")}>
          {lan.lan_open ? "局域网已开放" : "仅本机可访问"}
        </span>
        {lan.url ? <span class="chip2 hero">{lan.url}</span> : null}
      </div>
      {lan.lan_open ? (
        <div class="muted perm-note">
          手机浏览器打开上方地址,「添加到主屏幕」即得 App 图标;
          Bark 推送不依赖页面在线, 关屏也能收到低价提醒。
        </div>
      ) : (
        <div class="warn-box">
          当前只绑定了 127.0.0.1, 手机无法访问。在本机 PowerShell 运行
          <b> tools/enable_lan.ps1 </b>一键开放(改绑定+防火墙+重启),
          加 <b>-Revert</b> 可随时收回。仅建议在家庭 Wi-Fi 下开放。
        </div>
      )}
    </div>
  );
}

// cfg is lifted to App: shared with SourcesView so saving here cannot
// silently overwrite unsaved source toggles held in the other tab (and vice versa)
export default function PushView({ cfg, setCfg, cfgErr }) {
  const [alerts, setAlerts] = useState([]);
  const [rep, setRep] = useState(null);
  const [drops, setDrops] = useState([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [perm, setPerm] = useState(
    typeof Notification !== "undefined" ? Notification.permission : "unsupported"
  );
  const load = () => fetchAlerts()
    .then((a) => setAlerts(a.alerts || []))
    .catch((e) => setMsg("提醒历史加载失败: " + (e.message || e)));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    fetchWeekly().then((r) => setRep(r)).catch(() => {});
  }, []);
  useEffect(() => {
    fetchDrops().then((d) => setDrops(d.drops || [])).catch(() => {});
  }, []);
  if (!cfg) return <div class="card"><div class="empty">{cfgErr || "加载中…"}</div></div>;
  const push = cfg.push || {};
  const al = cfg.alert || {};
  const setAl = (k, v) => setCfg(Object.assign({}, cfg, {
    alert: Object.assign({}, al, { [k]: v }),
  }));
  const set = (k, v) => setCfg(Object.assign({}, cfg, { push: Object.assign({}, push, { [k]: v }) }));
  const doSave = () => {
    setBusy(true); setMsg("保存中…");
    saveConfig(cfg)
      .then((r) => { setCfg(r.config); setMsg("已保存 ✅(下次查询生效)"); })
      .catch((e) => setMsg("保存失败: " + (e.message || e)))
      .finally(() => setBusy(false));
  };
  const doTest = () => {
    setBusy(true); setMsg("测试推送中…");
    testPush()
      .then((r) => setMsg("已发送 ✅ " + (r.results || []).join(" · ")))
      .catch((e) => setMsg("发送失败 " + (e.message || e)))
      .finally(() => setBusy(false));
  };
  const askPerm = () => {
    if (typeof Notification === "undefined") return;
    Notification.requestPermission().then((p) => { setPerm(p); setMsg("通知权限: " + p); });
  };
  const chBark = !!(rep && rep.channels && rep.channels.bark);
  const chSc = !!(rep && rep.channels && rep.channels.serverchan);
  const ready = chBark || chSc;
  const weeklyOn = !!(rep && rep.push_enabled);
  // v0.56: live re-gate with the *unsaved* input values so the panel
  // previews exactly what the next cycle would alert on.
  const gp = Number(al.drop_pct == null || al.drop_pct === "" ? 15 : al.drop_pct) || 15;
  const ga = Number(al.drop_abs == null || al.drop_abs === "" ? 50 : al.drop_abs) || 0;
  const isSharp = (d) => d.delta < 0 && -d.pct >= gp && -d.delta >= ga;
  return (
    <div>
      <LanCard />
      <div class="card">
        <div class="card-head">
          <h3>推送状态</h3>
          <span class="sub">渠道就绪 · 周报开关 · 下次推送时间</span>
        </div>
        <div class="push-status">
          <span class={"chip2 " + (chBark ? "ok" : "plan")}>Bark {chBark ? "已配置" : "未配置"}</span>
          <span class={"chip2 " + (chSc ? "ok" : "plan")}>ServerChan {chSc ? "已配置" : "未配置"}</span>
          <span class={"chip2 " + (weeklyOn ? "ok" : "plan")}>周报推送 {weeklyOn ? "已开启" : "已关闭"}</span>
          {ready && weeklyOn ? (
            rep.push_due ? <span class="chip2 hero">下次推送: 已到期,下轮查询自动发</span>
              : (rep.next_push_at ? <span class="chip2">下次推送: {fmtTs(rep.next_push_at)}</span> : null)
          ) : null}
          {rep && rep.retry_waiting ? <span class="chip2 plan">上次失败,退避重试中</span> : null}
          {rep && rep.last_push_at ? <span class="chip2 plan">上次推送: {fmtTs(rep.last_push_at)}</span> : null}
        </div>
        {!ready ? (
          <div class="warn-box">
            推送渠道未就绪: 周报与低价提醒都无法送达。Bark 三步接入:
            ① App Store 安装 Bark App; ② 打开 App 复制专属 Key;
            ③ 填到上方 Bark Key 输入框并保存, 点「发送测试推送」验证。
            微信用户可改用 ServerChan (sct.ftqq.com 微信扫码即得 SendKey)。
          </div>
        ) : null}
      </div>
      <div class="card">
        <div class="card-head">
          <h3>📉 骤降提醒</h3>
          <span class="sub">大幅变便宜立即知道 · 无需等到破心理价位</span>
        </div>
        <div class="push-grid">
          <Field label="降幅百分比 ≥(%)">
            <input type="number" min="1" max="90"
              value={al.drop_pct == null ? 15 : al.drop_pct}
              onInput={(e) => setAl("drop_pct", e.target.value)} />
          </Field>
          <Field label="降幅金额 ≥(元)">
            <input type="number" min="0" max="5000"
              value={al.drop_abs == null ? 50 : al.drop_abs}
              onInput={(e) => setAl("drop_abs", e.target.value)} />
          </Field>
        </div>
        <div class="muted perm-note">
          两个条件同时满足才提醒(如 ≥15% 且 ≥50 元), 每条路线每天最多提醒一次;
          改动下方列表即时预演, 点上方「保存配置」后下轮查询生效。
        </div>
        {drops.length ? (
          <div class="drop-list">
            {drops.map((d) => (
              <div class="drop-row" key={d.route_id}>
                <span class="d-route">{d.from_city} → {d.to_city}</span>
                <span class="num">¥{Math.round(d.prev)} → ¥{Math.round(d.today)}</span>
                <span class={"d-delta " + (d.delta < 0 ? "down" : "up")}>
                  {(d.delta < 0 ? "▼" : "▲") + " ¥" + Math.abs(Math.round(d.delta)) + " (" + d.pct + "%)"}
                </span>
                <span class={"chip2 " + (isSharp(d) ? "hero" : "plan")}>
                  {isSharp(d) ? "会提醒" : "未达双闸"}
                </span>
              </div>
            ))}
          </div>
        ) : <div class="muted">归档两个查询日后, 这里显示每条路线的逐日环比与是否触发。</div>}
      </div>
      <div class="card">
        <div class="card-head">
          <h3>🔔 提醒推送</h3>
          <span class="sub">Bark=iPhone 通知 · ServerChan=微信</span>
        </div>
        <div class="push-grid">
          <Field label="Bark Key (iPhone)">
            <input type="text" placeholder="App 内复制的 Key, 留空禁用" value={push.bark_key || ""}
              onInput={(e) => set("bark_key", e.target.value.trim())} />
          </Field>
          <Field label="ServerChan SendKey (微信)">
            <input type="text" placeholder="sct 开头, 留空禁用" value={push.serverchan_sendkey || ""}
              onInput={(e) => set("serverchan_sendkey", e.target.value.trim())} />
          </Field>
          <Field label="推送分组">
            <input type="text" value={push.group || ""} onInput={(e) => set("group", e.target.value)} />
          </Field>
          <Field label="提示音(Bark)">
            <input type="text" placeholder="calm" value={push.sound || ""}
              onInput={(e) => set("sound", e.target.value.trim())} />
          </Field>
        </div>
        <label class="chk-row">
          <input type="checkbox" checked={!!push.weekly_enabled}
            onChange={(e) => set("weekly_enabled", e.target.checked)} />
          每 7 天自动推送一次价格周报
        </label>
        <div class="row-btns">
          <button class="btn primary" disabled={busy} onClick={doSave}>保存配置</button>
          <button class="btn" disabled={busy} onClick={doTest}>发送测试推送</button>
          {perm !== "granted" && perm !== "unsupported" ? (
            <button class="btn" onClick={askPerm}>开启浏览器通知</button>
          ) : null}
          {msg ? <span class="muted push-msg">{msg}</span> : null}
        </div>
        <div class="muted perm-note">
          浏览器通知权限: {perm === "granted" ? "已开启(页面在线时跨页系统通知)"
            : perm === "denied" ? "已被浏览器拒(地址栏图标里重置)"
            : perm === "unsupported" ? "当前环境不支持" : "未开启, 点上方按钮"}
           · 手机推送以 Bark/ServerChan 为准, 浏览器通知只是页面在线时的补充。
        </div>
      </div>
      <div class="card">
        <div class="card-head">
          <h3>🧾 提醒历史</h3>
          <span class="sub">低于心理价位时才推送</span>
        </div>
        {alerts.length ? alerts.map((a) => (
          <div class="alert-item2" key={String(a.ts || "") + String(a.title || "")}>
            <div class="a-title2">{a.title}</div>
            <div class="a-meta2">{String(a.ts || "").replace("T", " ")}{a.route ? " · " + a.route : ""}</div>
            <div class="a-body2">{a.body}</div>
            {a.url ? <a href={a.url} target="_blank" rel="noopener">购票链接 →</a> : null}
          </div>
        )) : <div class="muted">暂无提醒记录</div>}
      </div>
    </div>
  );
}
