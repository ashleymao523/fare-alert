import { useEffect, useState } from "preact/hooks";
import { fmtMoney, weekday, isRefDeal } from "../lib/data.js";

export default function AlertFloat({ route, onView }) {
  const [msg, setMsg] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    if (!route || !route.deals) return;
    const key = "farealert_seen_" + route.id;
    let seen = {};
    try { seen = JSON.parse(localStorage.getItem(key) || "{}"); } catch (e) { /* noop */ }
    const fresh = route.deals.filter((d) => d.below && !isRefDeal(d) && !seen[d.date]);
    if (!fresh.length) { setMsg(null); return; }
    let cheapest = fresh[0];
    fresh.forEach((d) => { if (d.total_price < cheapest.total_price) cheapest = d; });
    fresh.forEach((d) => { seen[d.date] = 1; });
    try { localStorage.setItem(key, JSON.stringify(seen)); } catch (e) { /* noop */ }
    setMsg({
      title: route.from_city + "→" + route.to_city + " 有 " + fresh.length + " 天低于心理价位",
      sub: "最低 " + fmtMoney(cheapest.total_price) + " · " + cheapest.date + " " + weekday(cheapest.date),
      date: cheapest.date
    });
    if (navigator.vibrate) { try { navigator.vibrate([120, 60, 120]); } catch (e) { /* noop */ } }
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      try {
        new Notification("FareAlert 低价提醒", {
          body: route.from_city + "→" + route.to_city + " 最低 " +
            fmtMoney(cheapest.total_price) + " (" + cheapest.date + ")",
          icon: "/static/icon.svg"
        });
      } catch (e) { /* noop */ }
    }
  }, [route && route.id, route && route.updated_at]);
  if (!msg || dismissed) return null;
  return (
    <div class="alert-float show">
      <span class="af-icon">🔔</span>
      <div>
        <div class="af-title">{msg.title}</div>
        <div class="af-sub">{msg.sub}</div>
      </div>
      <button class="af-btn" onClick={() => { setDismissed(true); onView(msg.date); }}>查看</button>
      <button class="af-close" onClick={() => setDismissed(true)}>×</button>
    </div>
  );
}
