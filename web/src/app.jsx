import { useEffect, useState } from "preact/hooks";
import { fetchSnapshot, fetchCityPhoto } from "./lib/api.js";
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

export function App() {
  const [snap, setSnap] = useState(null);
  const [err, setErr] = useState("");
  const [routeId, setRouteId] = useState("");
  const [selDate, setSelDate] = useState(null);
  const [calView, setCalView] = useState("cal");
  const [photos, setPhotos] = useState({});

  useEffect(() => {
    fetchSnapshot()
      .then((j) => setSnap(j))
      .catch((e) => setErr(String(e)));
  }, []);

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
        {err ? <div class="card"><div class="empty">快照加载失败: {err}</div></div> : null}
        {!snap && !err ? <div class="card"><div class="empty">加载中…</div></div> : null}
        {routes.length > 1 && (
          <div class="route-tabs">
            {routes.map((r) => (
              <button
                class={"rt-chip" + (route && r.id === route.id ? " active" : "")}
                onClick={() => { setRouteId(r.id); setSelDate(null); }}
              >
                {r.from_city}{r.trip_type === "roundtrip" ? " ⇄ " : " → "}{r.to_city}
              </button>
            ))}
          </div>
        )}
        {route ? (
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
              v2 预览 · 爬虫监控/线路管理/预算找目的地/周报/数据源/推送/日志请先到
              <a href="/">经典版</a> 操作 · 逐 tab 迁移中 · Preact + Vite
            </div>
          </div>
        ) : null}
        {snap && !routes.length && !err ? (
          <div class="card"><div class="empty">快照中暂无线路, 请先在经典版添加线路并执行查询</div></div>
        ) : null}
      </div>
      {route ? <AlertFloat route={route} onView={setSelDate} /> : null}
    </div>
  );
}
