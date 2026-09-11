// 与经典版 app.js 逐函数对齐的数据口径, 保证 v2 显示与旧版一致.
export const WEEK = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

export function fmtMoney(v) {
  const n = Math.round(v * 10) / 10;
  return "¥" + (n % 1 === 0 ? n.toFixed(0) : n.toFixed(1));
}

export function parseDate(s) { return new Date(s + "T00:00:00"); }

// Local-timezone YYYY-MM-DD (toISOString shifts back a day in UTC+8)
const dstrLocal = (d) => d.getFullYear() + "-" +
  String(d.getMonth() + 1).padStart(2, "0") + "-" +
  String(d.getDate()).padStart(2, "0");

export function fmtMD(s) {
  const d = parseDate(s);
  return (d.getMonth() + 1) + "/" + d.getDate();
}

export function weekday(s) { return WEEK[parseDate(s).getDay()]; }

export function dayList(route) {
  const days = [];
  if (!route || !route.window) return days;
  const d = parseDate(route.window[0]);
  const end = parseDate(route.window[1]);
  let guard = 0;
  while (d <= end && guard < 400) {
    days.push(dstrLocal(d));
    d.setDate(d.getDate() + 1);
    guard++;
  }
  return days;
}

export function heatClass(total, th) {
  const r = total / th;
  if (r < 0.85) return "h3";
  if (r < 0.95) return "h2";
  if (r < 1.0) return "h1";
  if (r < 1.15) return "h4";
  return "h5";
}

export function trainSeats(t) {
  if (t.seats && Object.keys(t.seats).length) return t.seats;
  if (t.second_class) return { "二等座": t.second_class };
  return {};
}

export function studentEst(seats) {
  if (seats["二等座"]) return seats["二等座"] * 0.75;
  if (seats["硬卧"] && seats["硬座"]) return seats["硬卧"] - seats["硬座"] * 0.5;
  if (seats["硬座"]) return seats["硬座"] * 0.5;
  return null;
}

export function trainMinPrice(t) {
  const s = trainSeats(t);
  const vs = Object.keys(s).map((k) => s[k]);
  return vs.length ? Math.min.apply(null, vs) : null;
}

export function cheapestFlight(route) {
  const ds = ((route && route.deals) || []).filter(
    (d) => d.source !== "nearby-ref" && d.source !== "interp"
  );
  if (!ds.length) return null;
  let best = ds[0];
  for (let i = 1; i < ds.length; i++) {
    if (ds[i].total_price < best.total_price) best = ds[i];
  }
  return best;
}

export function collectTrains(route) {
  const out = [];
  const errors = [];
  const info = route && route.train;
  if (!info || !info.pairs) return { fares: out, errors };
  Object.keys(info.pairs).forEach((pair) => {
    const items = info.pairs[pair];
    if (!Array.isArray(items)) {
      if (items && items.error) errors.push(pair + ": " + items.error);
      return;
    }
    items.forEach((it) => {
      it.pair = it.pair || pair;
      out.push(it);
    });
  });
  return { fares: out, errors };
}

export function trainBest(route) {
  const t = collectTrains(route);
  let second = null;
  let sleeper = null;
  t.fares.forEach((f) => {
    const seats = trainSeats(f);
    const ze = seats["二等座"];
    if (ze && (!second || ze < trainSeats(second)["二等座"])) second = f;
    let sl = null;
    Object.keys(seats).forEach((lab) => {
      if (lab.indexOf("卧") < 0) return;
      if (!sl || seats[lab] < seats[sl]) sl = lab;
    });
    if (sl) {
      const price = seats[sl];
      if (!sleeper || price < sleeper.price) sleeper = { train: f, label: sl, price };
    }
  });
  return { second, sleeper, all: t.fares, errors: t.errors };
}

// RT 往返口径: combined_by_date[date] = {total, ret_date, out_total, ret_total, ret_flight, url}
export function dealForDate(route, date) {
  const isRT = !!(route.trip_type === "roundtrip" && route.combined_by_date);
  const base = (route.deals || []).find((d) => d.date === date);
  if (!base) return null;
  if (!isRT) return base;
  const cd = route.combined_by_date[date];
  if (!cd) return base;
  return Object.assign({}, base, {
    total_price: cd.total,
    ret_date: cd.ret_date,
    out_total: cd.out_total,
    ret_total: cd.ret_total,
    ret_flight: cd.ret_flight,
    url: cd.url || base.url
  });
}

export function isRefDeal(d) {
  return d && (d.source === "nearby-ref" || d.source === "interp");
}
