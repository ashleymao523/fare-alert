import { useEffect, useState } from "preact/hooks";
import { fetchSnapshot, fetchCityPhoto, fetchConfig } from "./lib/api.js";
import Header from "./components/Header.jsx";
import Hero from "./components/Hero.jsx";
import Kpis from "./components/Kpis.jsx";
import Verdict from "./components/Verdict.jsx";
import DestIntel from "./components/DestIntel.jsx";
import CalendarView from "./components/CalendarView.jsx";
import DayDetail from "./components/DayDetail.jsx";
import TrendChart from "./components/TrendChart.jsx";
import Top5 from "./components/Top5.jsx";
import Trains from "./components/Trains.jsx";
import AlertFloat from "./components/AlertFloat.jsx";
import CrawlView from "./components/CrawlView.jsx";
import WeeklyView from "./components/WeeklyView.jsx";
import SourcesView from "./components/SourcesView.jsx";
import PushView from "./components/PushView.jsx";
import RoutesView from "./components/RoutesView.jsx";
import ReverseView from "./components/ReverseView.jsx";
import LogsView from "./components/LogsView.jsx";

const TABS = [
  ["dash", "📊 仪表盘"],
  ["routes", "🧭 线路"],
  ["reverse", "🧭 预算找目的地"],
  ["crawl", "🕷 爬虫监控"],
  ["weekly", "📈 周报"],
  ["sources", "🔌 数据源"],
  ["push", "🔔 推送"],
  ["logs", "📜 日志"],
];

const TAB_IDS = TABS.map(([id]) => id);

function tabFromHash() {
  const h = (location.hash || "").replace(/^#\/?/, "");
  return TAB_IDS.includes(h) ? h : "dash";
}

export function App() {
  const [snap, setSnap] = useState(null);
  const [err, setErr] = useState("");
  const [routeId, setRouteId] = useState("");
  const [selDate, setSelDate] = useState(null);
  const [calView, setCalView] = useState("cal");
  const [photos, setPhotos] = useState({});
  const [tab, setTab] = useState(tabFromHash);
  const [cfg, setCfg] = useState(null);
  const [cfgMeta, setCfgMeta] = useState({});
  const [cfgErr, setCfgErr] = useState("");

  useEffect(() => {
    fetchSnapshot()
      .then((j) => setSnap(j))
      .catch((e) => setErr(String(e)));
    fetchConfig()
      .then((c) => { setCfg(c.config); setCfgMeta(c.sources || {}); })
      .catch((e) => setCfgErr("配置加载失败: " + (e.message || e)));
  }, []);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const switchTab = (id) => {
    setTab(id);
    if ("#" + id !== location.hash) {
      history.replaceState(null, "", "#" + id);
    }
  };

  const routes = (snap && snap.routes) || [];
  const route = routes.find((r) => r.id === routeId) || routes[0] || null;

  useEffect(() => {
    if (!route) return;
    [route.from_city, route.to_city].forEach((c) => {
      if (!c) return;
      fetchCityPhoto(c)
        .then((j) => {
          setPhotos((p) => Object.assign({}, p, { [c]: j && j.ok ? j.photo : null }));
        })
        .catch(() => {
          setPhotos((p) => Object.assign({}, p, { [c]: null }));
        });
    });
  }, [route && route.id]);

  const isRT = !!(route && route.trip_type === "roundtrip");
  return (
    <div>
      <Header snap={snap} />
      <div class="wrap">
        <nav class="tabbar">
          {TABS.map(([id, label]) => (
            <button key={id} class={"tab-btn" + (tab === id ? " active" : "")}
              onClick={() => switchTab(id)}>{label}</button>
          ))}
        </nav>
        {tab === "routes" ? (
          <RoutesView cfg={cfg} setCfg={setCfg} cfgErr={cfgErr} />
        ) : null}
        {tab === "reverse" ? <ReverseView /> : null}
        {tab === "logs" ? <LogsView /> : null}
        {tab === "crawl" ? <CrawlView /> : null}
        {tab === "weekly" ? <WeeklyView /> : null}
        {tab === "sources" ? (
          <SourcesView snap={snap} cfg={cfg} setCfg={setCfg} meta={cfgMeta} setMeta={setCfgMeta} cfgErr={cfgErr} />
        ) : null}
        {tab === "push" ? <PushView cfg={cfg} setCfg={setCfg} cfgErr={cfgErr} /> : null}
        {err ? <div class="card"><div class="empty">快照加载失败: {err}</div></div> : null}
        {!snap && !err && tab === "dash" ? <div class="card"><div class="empty">加载中…</div></div> : null}
        {routes.length > 1 && tab === "dash" && (
          <div class="route-tabs">
            {routes.map((r) => (
              <button
                key={r.id}
                class={"rt-chip" + (route && r.id === route.id ? " active" : "")}
                onClick={() => { setRouteId(r.id); setSelDate(null); }}
              >
                {r.from_city}{r.trip_type === "roundtrip" ? " ⇄ " : " → "}{r.to_city}
              </button>
            ))}
          </div>
        )}
        {route && tab === "dash" ? (
          <div>
            <Hero route={route} photos={photos} />
            <Kpis route={route} />
            <Verdict route={route} />
            <DestIntel route={route} />
            <CalendarView
              route={route}
              selDate={selDate}
              onSelect={setSelDate}
              view={calView}
              onView={setCalView}
            />
            <DayDetail route={route} date={selDate} />
            <TrendChart
              route={route}
              dealsKey="deals"
              title={isRT ? "往返合计趋势 (按去程日期)" : "价格趋势"}
              hint="绿点=低于心理价位 · 悬停看明细 · 灰点=临近日参考 · 琥珀点=插值估算"
            />
            {isRT && (route.return_deals || []).length ? (
              <TrendChart
                route={route}
                dealsKey="return_deals"
                title="返程趋势"
                hint="按返程日期 · 绿点=低于心理价位"
              />
            ) : null}
            <Top5 route={route} />
            <Trains route={route} />
            <div class="foot">
              v2 · 全部 8 个功能页已迁移 · Preact + Vite ·
              <a href="/classic">经典版</a>
            </div>
          </div>
        ) : null}
        {snap && !routes.length && !err && tab === "dash" ? (
          <div class="card"><div class="empty">快照中暂无线路, 请先在经典版添加线路并执行查询</div></div>
        ) : null}
      </div>
      {route ? <AlertFloat route={route} onView={setSelDate} /> : null}
    </div>
  );
}
