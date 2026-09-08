"use strict";
(function () {
  var S = {
    cfg: null, secrets: null, sources: null,
    snap: null, routeId: null, selDate: null,
    cities: null, stations: null,
    _citiesReq: null, _stationsReq: null
  };
  var WEEK = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

  function $(id) { return document.getElementById(id); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function fmtMoney(v) {
    var n = Math.round(v * 10) / 10;
    return "¥" + (n % 1 === 0 ? n.toFixed(0) : n.toFixed(1));
  }
  function parseDate(s) { return new Date(s + "T00:00:00"); }
  function fmtMD(s) {
    var d = parseDate(s);
    return (d.getMonth() + 1) + "/" + d.getDate();
  }
  function weekday(s) { return WEEK[parseDate(s).getDay()]; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function toast(msg) {
    var t = $("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._tm);
    t._tm = setTimeout(function () { t.classList.remove("show"); }, 2800);
  }

  function api(path, opts) {
    return fetch(path, opts).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok || j.ok === false) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    });
  }
  function post(path, body) {
    return api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
  }

  function curRoute() {
    if (!S.snap || !S.snap.routes || !S.snap.routes.length) return null;
    var list = S.snap.routes;
    for (var i = 0; i < list.length; i++) if (list[i].id === S.routeId) return list[i];
    return list[0];
  }

  /* ---------- 联想数据源 ---------- */

  function ensureCities() {
    if (S.cities || S._citiesReq) return S._citiesReq;
    S._citiesReq = api("/api/cities").then(function (r) {
      S.cities = r.cities || [];
      return S.cities;
    });
    return S._citiesReq;
  }

  function ensureStations() {
    if (S.stations || S._stationsReq) return S._stationsReq;
    S._stationsReq = api("/api/stations").then(function (r) {
      S.stations = r.stations || [];
      return S.stations;
    }).catch(function (e) {
      S._stationsReq = null;
      throw e;
    });
    return S._stationsReq;
  }

  function filterAC(list, q, limit) {
    q = (q || "").trim().toLowerCase();
    var out = [];
    for (var i = 0; i < list.length && out.length < (limit || 8); i++) {
      var c = list[i];
      var name = c.name || "";
      if (!q || name.indexOf(q) >= 0 ||
          (c.pinyin || "").indexOf(q) >= 0 || (c.py || "").indexOf(q) >= 0) {
        out.push(c);
      }
    }
    return out;
  }

  function attachAC(input, opts) {
    var wrap = input.parentNode;
    if (!wrap || !wrap.classList || !wrap.classList.contains("ac-wrap")) return;
    var list = el("div", "ac-list hidden");
    wrap.appendChild(list);
    var items = [], active = -1;

    function close() { list.classList.add("hidden"); items = []; active = -1; }
    function draw() {
      list.textContent = "";
      if (!items.length) {
        list.appendChild(el("div", "ac-item", opts.emptyText || "无匹配(可直接输入中文全称)"));
        return;
      }
      items.forEach(function (it, i) {
        var d = el("div", "ac-item" + (i === active ? " active" : ""));
        d.appendChild(el("span", "ac-label", it.name));
        if (it.sub) d.appendChild(el("span", "ac-sub", it.sub));
        d.addEventListener("mousedown", function (ev) {
          ev.preventDefault();
          pick(i);
        });
        list.appendChild(d);
      });
    }
    function pick(i) {
      var it = items[i];
      if (!it) return;
      input.value = it.name;
      if (opts.onPick) opts.onPick(it);
      close();
    }
    function refresh() {
      var src = opts.source();
      if (src == null) {
        list.classList.remove("hidden");
        list.textContent = "";
        list.appendChild(el("div", "ac-item", "加载中…"));
        return;
      }
      items = filterAC(src, input.value);
      active = items.length ? 0 : -1;
      list.classList.remove("hidden");
      draw();
    }
    input.addEventListener("focus", function () {
      if (opts.source() == null) opts.load();
      refresh();
    });
    input.addEventListener("input", function () {
      if (opts.source() == null) opts.load();
      refresh();
      if (opts.onInput) opts.onInput();
    });
    input.addEventListener("keydown", function (ev) {
      if (list.classList.contains("hidden")) return;
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        if (items.length) { active = (active + 1) % items.length; draw(); }
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        if (items.length) { active = (active - 1 + items.length) % items.length; draw(); }
      } else if (ev.key === "Enter") {
        ev.preventDefault();
        if (active >= 0) pick(active);
      } else if (ev.key === "Escape") {
        close();
      }
    });
    input.addEventListener("blur", function () { setTimeout(close, 150); });
  }

  function acField(labelText, value, load, source, onChange, placeholder) {
    var root = el("label", "field grow");
    var cap = el("span", "f-label", labelText);
    var acw = el("div", "ac-wrap");
    var input = el("input");
    input.type = "text";
    input.value = value || "";
    input.placeholder = placeholder || "输入中文或拼音";
    acw.appendChild(input);
    attachAC(input, {
      load: load, source: source,
      onPick: function (it) { onChange(it.name); },
      onInput: function () { onChange(input.value); }
    });
    root.appendChild(cap);
    root.appendChild(acw);
    return { root: root, input: input };
  }

  /* ---------- 仪表盘 ---------- */

  function collectTrains(route) {
    var out = [], errors = [];
    var info = route && route.train;
    if (!info || !info.pairs) return { fares: out, errors: errors };
    Object.keys(info.pairs).forEach(function (pair) {
      var items = info.pairs[pair];
      if (!Array.isArray(items)) {
        if (items && items.error) errors.push(pair + ": " + items.error);
        return;
      }
      items.forEach(function (it) { it.pair = it.pair || pair; out.push(it); });
    });
    return { fares: out, errors: errors };
  }

  function trainSeats(t) {
    if (t.seats && Object.keys(t.seats).length) return t.seats;
    if (t.second_class) return { "二等座": t.second_class };
    return {};
  }

  function studentEst(seats) {
    if (seats["二等座"]) return seats["二等座"] * 0.75;
    if (seats["硬卧"] && seats["硬座"]) return seats["硬卧"] - seats["硬座"] * 0.5;
    if (seats["硬座"]) return seats["硬座"] * 0.5;
    return null;
  }

  function trainMinPrice(t) {
    var s = trainSeats(t);
    var vs = Object.keys(s).map(function (k) { return s[k]; });
    return vs.length ? Math.min.apply(null, vs) : null;
  }

  function cheapestFlight(route) {
    var ds = (route && route.deals) || [];
    if (!ds.length) return null;
    var best = ds[0];
    for (var i = 1; i < ds.length; i++) if (ds[i].total_price < best.total_price) best = ds[i];
    return best;
  }

  function trainBest(route) {
    var t = collectTrains(route);
    var second = null, sleeper = null;
    t.fares.forEach(function (f) {
      var seats = trainSeats(f);
      var ze = seats["二等座"];
      if (ze && (!second || ze < trainSeats(second)["二等座"])) second = f;
      var sl = null;
      Object.keys(seats).forEach(function (lab) {
        if (lab.indexOf("卧") < 0) return;
        if (!sl || seats[lab] < seats[sl]) sl = lab;
      });
      if (sl) {
        var price = seats[sl];
        if (!sleeper || price < sleeper.price) sleeper = { train: f, label: sl, price: price };
      }
    });
    return { second: second, sleeper: sleeper, all: t.fares, errors: t.errors };
  }

  function renderKpis(route) {
    var box = $("kpis");
    box.textContent = "";
    if (!route || !route.deals || !route.deals.length) {
      var c = el("div", "kpi");
      c.appendChild(el("div", "k-label", "暂无数据"));
      c.appendChild(el("div", "k-value", route ? (route.flight_source_status || "-") : "-"));
      box.appendChild(c);
      return;
    }
    var f = cheapestFlight(route);
    var tr = trainBest(route);
    var items = [];
    items.push({
      label: "最低机票总价", value: fmtMoney(f.total_price),
      sub: f.date + " " + weekday(f.date) + " · " + f.flight_no,
      cls: f.total_price < route.threshold_total ? "good" : "",
      url: f.url
    });
    items.push({
      label: "低于心理价位", value: route.days_below + " 天",
      sub: "窗口 " + route.window[0] + " ~ " + route.window[1],
      cls: route.days_below > 0 ? "good" : "warn"
    });
    items.push({ label: "心理价位(含税)", value: fmtMoney(route.threshold_total), sub: "低于即推送提醒" });
    if (tr.second) {
      var ze = trainSeats(tr.second)["二等座"];
      items.push({
        label: "列车二等最低", value: fmtMoney(ze),
        sub: tr.second.train_code + " " + tr.second.dep_time + "开 · 历时" + tr.second.duration_text,
        url: tr.second.url
      });
      items.push({
        label: "学生动车 ≈", value: fmtMoney(ze * 0.75),
        sub: "二等座公布价75折估算 · 点击直达12306", cls: "good",
        url: tr.second.url
      });
    }
    if (tr.sleeper) {
      items.push({
        label: "最低卧铺", value: fmtMoney(tr.sleeper.price),
        sub: tr.sleeper.train.train_code + " " + tr.sleeper.label + " · 历时" + tr.sleeper.train.duration_text,
        cls: "good",
        url: tr.sleeper.train.url
      });
    }
    items.forEach(function (it) {
      var k = it.url ? el("a", "kpi" + (it.cls ? " " + it.cls : ""))
                      : el("div", "kpi" + (it.cls ? " " + it.cls : ""));
      if (it.url) {
        k.href = it.url;
        k.target = "_blank";
        k.rel = "noopener";
        k.title = "点击直达购票/查票页";
      }
      k.appendChild(el("div", "k-label", it.label));
      k.appendChild(el("div", "k-value", it.value));
      k.appendChild(el("div", "k-sub", it.sub));
      box.appendChild(k);
    });
  }

  function renderVerdict(route) {
    var box = $("verdict");
    box.textContent = "";
    if (!route || !route.deals || !route.deals.length) return;
    var f = cheapestFlight(route);
    var tr = trainBest(route);
    var t = tr.second;
    var ze = t ? trainSeats(t)["二等座"] : null;
    var s = t ? ze * 0.75 : null;
    var sl = tr.sleeper;

    var names = { flight: "✈️ 机票", train: "🚄 动车二等座", student: "🎓 学生动车", sleeper: "🛏️ 列车卧铺" };
    var cands = [{ k: "flight", p: f.total_price }];
    if (t) cands.push({ k: "train", p: ze });
    if (t) cands.push({ k: "student", p: s });
    if (sl) cands.push({ k: "sleeper", p: sl.price });
    cands.sort(function (a, b) { return a.p - b.p; });
    var winner = cands[0].k;
    var save = cands.length > 1 ? cands[1].p - cands[0].p : null;

    var banner = el("div", "verdict-banner");
    banner.appendChild(el("b", null, "当前最优: " + names[winner]));
    banner.appendChild(document.createTextNode(
      (save != null ? ", 比次优方案省约 " + fmtMoney(save) : "") +
      "。时间成本参考: 飞机含提前值机约4-5小时; 动车历时8-15小时, 夕发朝至可车上过夜省一晚住宿。"));
    box.appendChild(banner);

    var cards = el("div", "verdict-cards");
    function vcard(kind, isBest, title, price, sub, url) {
      var c = el("div", "vcard" + (isBest ? " best" : ""));
      if (isBest) c.appendChild(el("div", "v-tag", "最优"));
      c.appendChild(el("div", "v-title", title));
      c.appendChild(el("div", "v-price", price));
      var sd = el("div", "v-sub");
      sd.innerHTML = sub;
      c.appendChild(sd);
      if (url) {
        var a = el("a", "v-link");
        a.href = url;
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = "去查票/下单 →";
        c.appendChild(a);
      }
      return c;
    }
    cards.appendChild(vcard("flight", winner === "flight",
      "✈️ 最低机票 (" + f.date + ")", fmtMoney(f.total_price),
      esc(f.flight_no + " " + f.airline) + " · 裸价" + fmtMoney(f.bare_price) + "+税费<br>" +
      "行李: " + esc(f.baggage) + "<br>起降时刻/飞行时长以下单页为准"), f.url);
    if (t) {
      cards.appendChild(vcard("train", winner === "train",
        "🚄 动车二等 (" + t.train_code + ")", fmtMoney(ze),
        esc(t.pair.replace("-", " → ")) + " · " + esc(t.dep_time) + "-" + esc(t.arr_time) +
        " 历时" + esc(t.duration_text), t.url));
      cards.appendChild(vcard("student", winner === "student",
        "🎓 学生动车 ≈", fmtMoney(s),
        "二等座公布票价75折估算<br>资格/优惠区间以12306下单页为准", t.url));
    }
    if (sl) {
      var slStu = studentEst(trainSeats(sl.train));
      cards.appendChild(vcard("sleeper", winner === "sleeper",
        "🛏️ 卧铺 (" + sl.train.train_code + " " + sl.label + ")", fmtMoney(sl.price),
        esc(sl.train.pair.replace("-", " → ")) + " · " + esc(sl.train.dep_time) + "-" + esc(sl.train.arr_time) +
        " 历时" + esc(sl.train.duration_text) +
        (slStu ? "<br>学生卧铺≈" + fmtMoney(slStu) : ""), sl.train.url));
    }
    box.appendChild(cards);
  }

  function dayList(route) {
    var days = [];
    if (!route || !route.window) return days;
    var d = parseDate(route.window[0]), end = parseDate(route.window[1]);
    var guard = 0;
    while (d <= end && guard < 400) {
      days.push(d.toISOString().slice(0, 10));
      d.setDate(d.getDate() + 1);
      guard++;
    }
    return days;
  }

  function heatClass(total, th) {
    var r = total / th;
    if (r < 0.85) return "h3";
    if (r < 0.95) return "h2";
    if (r < 1.0) return "h1";
    if (r < 1.15) return "h4";
    return "h5";
  }

  function renderCalendar(route) {
    var box = $("calendar");
    box.textContent = "";
    $("calMeta").textContent = route ? ("点击日期看详情 · 阈值 " + fmtMoney(route.threshold_total)) : "";
    if (!route) return;
    var map = {};
    (route.deals || []).forEach(function (d) { map[d.date] = d; });
    dayList(route).forEach(function (ds) {
      var d = map[ds];
      var cls = "day " + (d ? heatClass(d.total_price, route.threshold_total) : "empty");
      if (ds === S.selDate) cls += " selected";
      var c = el("div", cls);
      c.appendChild(el("div", "d-date", fmtMD(ds)));
      c.appendChild(el("div", "d-week", weekday(ds)));
      c.appendChild(el("div", "d-price", d ? fmtMoney(d.total_price) : "—"));
      if (d) c.addEventListener("click", function () {
        S.selDate = (S.selDate === ds) ? null : ds;
        renderCalendar(route);
        renderDayDetail(route);
      });
      box.appendChild(c);
    });
  }

  function renderDayDetail(route) {
    var box = $("dayDetail");
    box.textContent = "";
    if (!route || !S.selDate) { box.classList.add("hidden"); return; }
    var map = {};
    (route.deals || []).forEach(function (d) { map[d.date] = d; });
    var d = map[S.selDate];
    box.classList.remove("hidden");
    if (!d) {
      box.appendChild(el("div", "dd-title", S.selDate + " " + weekday(S.selDate) + " · 该日无报价"));
      return;
    }
    var below = d.total_price < route.threshold_total;
    var title = el("div", "dd-title");
    title.appendChild(document.createTextNode(d.date + " " + weekday(d.date) + " " + fmtMoney(d.total_price)));
    var badge = el("span", "badge " + (below ? "green" : "gray"),
      below ? "低于心理价位" : "高于心理价位");
    title.appendChild(badge);
    box.appendChild(title);

    var warn = /不含|确认/.test(d.baggage) ? " ⚠️" : " 🧳";
    var line = el("div");
    line.innerHTML = esc(d.flight_no + " " + d.airline) + " · 裸价 " + fmtMoney(d.bare_price) +
      " + 机建燃油 = <b>" + fmtMoney(d.total_price) + "</b>" + warn + esc(d.baggage) +
      (d.alert ? " · <span class=\"badge green\">已推送提醒</span>" : "");
    box.appendChild(line);
    var tr = trainBest(route);
    var ftNote = el("div", "muted");
    ftNote.textContent = (d.dep_time && d.arr_time)
      ? ("起飞 " + d.dep_time + " · 到达 " + d.arr_time + (d.duration_text ? " · " + d.duration_text : ""))
      : "起降时刻/飞行时长以下单页为准(当前数据源仅提供每日最低价)";
    box.appendChild(ftNote);
    if (tr.second) {
      var t = tr.second;
      var ze = trainSeats(t)["二等座"];
      var ref = el("div", "muted");
      ref.textContent = "参考: " + t.train_code + " 二等 " + fmtMoney(ze) +
        " / 学生≈" + fmtMoney(ze * 0.75) +
        " (" + t.pair.replace("-", "→") + " " + t.dep_time + "出发)";
      box.appendChild(ref);
    }
    if (tr.sleeper) {
      var ref2 = el("div", "muted");
      ref2.textContent = "参考: " + tr.sleeper.train.train_code + " " + tr.sleeper.label + " " +
        fmtMoney(tr.sleeper.price) + " (夕发朝至可选)";
      box.appendChild(ref2);
    }
    var link = el("a", "btn small book-link");
    link.href = d.url;
    link.target = "_blank";
    link.textContent = "去哪儿购票页 →";
    box.appendChild(link);
  }

  function renderTrend(route) {
    var box = $("trend");
    if (!route || !route.deals || !route.deals.length) { box.textContent = "暂无数据"; return; }
    var pts = (route.deals || []).slice().sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    var th = route.threshold_total;
    var W = 760, H = 240, L = 48, R = 14, T = 16, B = 30;
    var lo = th, hi = th;
    pts.forEach(function (p) {
      if (p.total_price < lo) lo = p.total_price;
      if (p.total_price > hi) hi = p.total_price;
    });
    lo = lo * 0.92; hi = hi * 1.06;
    function X(i) { return L + (W - L - R) * (pts.length === 1 ? 0.5 : i / (pts.length - 1)); }
    function Y(v) { return T + (H - T - B) * (1 - (v - lo) / (hi - lo)); }

    var s = [];
    s.push("<svg viewBox=\"0 0 " + W + " " + H + "\" xmlns=\"http://www.w3.org/2000/svg\">");
    for (var g = 0; g <= 4; g++) {
      var v = lo + (hi - lo) * g / 4;
      var y = Y(v);
      s.push("<line x1=\"" + L + "\" y1=\"" + y + "\" x2=\"" + (W - R) + "\" y2=\"" + y +
             "\" stroke=\"#26324d\" stroke-width=\"1\"/>");
      s.push("<text x=\"" + (L - 6) + "\" y=\"" + (y + 4) + "\" fill=\"#8b98b4\" font-size=\"11\" text-anchor=\"end\">" + Math.round(v) + "</text>");
    }
    s.push("<line x1=\"" + L + "\" y1=\"" + Y(th) + "\" x2=\"" + (W - R) + "\" y2=\"" + Y(th) +
           "\" stroke=\"#ef4444\" stroke-width=\"1.5\" stroke-dasharray=\"6 4\"/>");
    s.push("<text x=\"" + (W - R) + "\" y=\"" + (Y(th) - 6) + "\" fill=\"#ef4444\" font-size=\"11\" text-anchor=\"end\">心理价位 " + fmtMoney(th) + "</text>");
    var poly = [];
    var minIdx = 0;
    for (var i = 0; i < pts.length; i++) {
      if (pts[i].total_price < pts[minIdx].total_price) minIdx = i;
      poly.push(X(i).toFixed(1) + "," + Y(pts[i].total_price).toFixed(1));
    }
    s.push("<polyline points=\"" + poly.join(" ") + "\" fill=\"none\" stroke=\"#4f8cff\" stroke-width=\"2\"/>");
    var step = Math.max(1, Math.ceil(pts.length / 8));
    for (var j = 0; j < pts.length; j++) {
      var p = pts[j];
      var color = p.total_price < th ? "#22c55e" : "#64748b";
      var r = j === minIdx ? 5 : 3;
      s.push("<circle cx=\"" + X(j).toFixed(1) + "\" cy=\"" + Y(p.total_price).toFixed(1) +
             "\" r=\"" + r + "\" fill=\"" + color + "\"><title>" +
             p.date + " " + weekday(p.date) + " " + fmtMoney(p.total_price) + " " + p.flight_no + "</title></circle>");
      if (j % step === 0) {
        s.push("<text x=\"" + X(j).toFixed(1) + "\" y=\"" + (H - 8) + "\" fill=\"#8b98b4\" font-size=\"10\" text-anchor=\"middle\">" + fmtMD(p.date) + "</text>");
      }
    }
    var mp = pts[minIdx];
    s.push("<text x=\"" + X(minIdx).toFixed(1) + "\" y=\"" + (Y(mp.total_price) - 10) +
           "\" fill=\"#22c55e\" font-size=\"12\" font-weight=\"bold\" text-anchor=\"middle\">" + fmtMoney(mp.total_price) + "</text>");
    s.push("</svg>");
    box.innerHTML = s.join("");
  }

  function renderTrains(route) {
    var box = $("trainBox");
    box.textContent = "";
    $("trainMeta").textContent = "";
    if (!route || !route.train || !route.train.pairs) {
      box.appendChild(el("div", "muted", "未启用列车对比或暂无数据(可在线路管理中开启)"));
      return;
    }
    $("trainMeta").textContent = "查询日 " + route.train.query_date + " · 更新于 " + String(route.train.updated_at || "").replace("T", " ");
    var tr = trainBest(route);
    tr.errors.forEach(function (e) {
      box.appendChild(el("div", "err-line", "⚠️ " + e));
    });
    if (!tr.all.length) {
      box.appendChild(el("div", "muted", "未查到车次"));
      return;
    }
    var sorted = tr.all.slice().sort(function (a, b) {
      return (trainMinPrice(a) || 9e9) - (trainMinPrice(b) || 9e9);
    });
    var wrap = el("div", "tbl-scroll");
    var tb = el("table", "tbl");
    tb.innerHTML = "<tr><th>车次</th><th>区间</th><th>时刻</th><th>历时</th><th>席位票价(12306查到即列)</th><th>学生≈</th><th>购票</th></tr>";
    var minP = trainMinPrice(sorted[0]);
    sorted.slice(0, 20).forEach(function (t) {
      var row = el("tr", (trainMinPrice(t) != null && trainMinPrice(t) === minP) ? "low" : "");
      function td(v) { var d = el("td"); d.textContent = v == null ? "--" : v; return d; }
      row.appendChild(td(t.train_code));
      row.appendChild(td(t.pair.replace("-", " → ")));
      row.appendChild(td(t.dep_time + " - " + t.arr_time));
      row.appendChild(td(t.duration_text));
      var seats = trainSeats(t);
      var keys = Object.keys(seats).sort(function (a, b) { return seats[a] - seats[b]; });
      var cell = el("td");
      var cellWrap = el("div", "seat-cell");
      keys.forEach(function (lab) {
        cellWrap.appendChild(el("span", "seat-chip" + (lab.indexOf("卧") >= 0 ? " sleep" : ""),
          lab + " " + fmtMoney(seats[lab])));
      });
      if (!keys.length) cellWrap.appendChild(el("span", "muted", "--"));
      cell.appendChild(cellWrap);
      row.appendChild(cell);
      var stu = studentEst(seats);
      row.appendChild(stu ? td(fmtMoney(stu)) : td("--"));
      var buy = el("td");
      if (t.url) {
        var bl = el("a", "btn small buy-link", "下单");
        bl.href = t.url;
        bl.target = "_blank";
        bl.rel = "noopener";
        buy.appendChild(bl);
      } else {
        buy.textContent = "--";
      }
      row.appendChild(buy);
      tb.appendChild(row);
    });
    wrap.appendChild(tb);
    box.appendChild(wrap);
    var note = el("div", "muted");
    note.style.marginTop = "8px";
    var hasOvernight = sorted.some(function (t) {
      var h = parseInt(t.dep_time.slice(0, 2), 10);
      return !isNaN(h) && h >= 18;
    });
    note.textContent = "含高铁/动车/直达/特快/快速列车, 12306查到什么席位就列什么(含卧铺) · " +
      "学生票估算: 动车组二等座75折/普速硬座5折/硬卧=硬卧-硬座半价, 以12306下单页为准" +
      (hasOvernight ? " · 有晚间出发车次(夕发朝至,车上过夜省一晚住宿)" : "") +
      " · 12306数据缓存24小时";
    box.appendChild(note);
  }

  function renderDash() {
    var route = curRoute();
    $("updatedAt").textContent = S.snap ? ("更新于 " + String(S.snap.updated_at || "").replace("T", " ")) : "";
    renderKpis(route);
    renderVerdict(route);
    renderCalendar(route);
    renderDayDetail(route);
    renderTrend(route);
    renderTrains(route);
  }

  function renderRouteTabs() {
    var box = $("routeTabs");
    box.textContent = "";
    if (!S.snap || !S.snap.routes) return;
    S.snap.routes.forEach(function (r) {
      var b = el("button", r.id === (S.routeId || (S.snap.routes[0] && S.snap.routes[0].id)) ? "active" : "",
        r.from_city + " → " + r.to_city);
      b.addEventListener("click", function () {
        S.routeId = r.id;
        S.selDate = null;
        renderRouteTabs();
        renderDash();
      });
      box.appendChild(b);
    });
  }

  /* ---------- 线路管理 ---------- */

  var ROUTE_TPLS = [
    { from: "杭州", to: "重庆", th: 500, pairs: [["杭州东", "重庆北"]] },
    { from: "重庆", to: "杭州", th: 500, pairs: [["重庆北", "杭州东"]] },
    { from: "杭州", to: "成都", th: 450, pairs: [["杭州东", "成都东"]] },
    { from: "成都", to: "杭州", th: 450, pairs: [["成都东", "杭州东"]] },
    { from: "杭州", to: "西安", th: 500, pairs: [["杭州东", "西安北"]] },
    { from: "杭州", to: "北京", th: 600, pairs: [["杭州东", "北京南"]] }
  ];

  function renderRoutesEditor() {
    var box = $("routesEditor");
    box.textContent = "";
    if (!S.cfg) return;
    ensureCities().catch(function () {});

    var tplRow = el("div", "tpl-row");
    tplRow.appendChild(el("span", "tpl-label", "快捷添加:"));
    ROUTE_TPLS.forEach(function (tp) {
      var b = el("button", "chip-btn", tp.from + " ✈ " + tp.to);
      b.addEventListener("click", function () {
        S.cfg.routes.push({
          id: "r" + Date.now().toString(36),
          from_city: tp.from,
          to_city: tp.to,
          window_days: 60,
          threshold_total: tp.th,
          train_compare: { enabled: true, station_pairs: tp.pairs.map(function (p) { return p.slice(); }) }
        });
        renderRoutesEditor();
      });
      tplRow.appendChild(b);
    });
    box.appendChild(tplRow);

    S.cfg.routes.forEach(function (r, idx) {
      box.appendChild(routeCard(r, idx));
    });
  }

  function routeCard(r, idx) {
    var card = el("div", "route-card");
    var head = el("div", "rc-head");
    var title = el("div", "rc-title", r.from_city + " → " + r.to_city);
    title.style.fontSize = "15px";
    var del = el("button", "btn danger small", "删除");
    del.addEventListener("click", function () {
      if (!confirm("确定删除线路 " + r.from_city + "→" + r.to_city + " ?")) return;
      S.cfg.routes.splice(idx, 1);
      renderRoutesEditor();
    });
    head.appendChild(title);
    head.appendChild(el("span", "muted", r.id));
    head.appendChild(del);
    card.appendChild(head);

    function refreshTitle() { title.textContent = r.from_city + " → " + r.to_city; }

    var line = el("div", "city-line");
    var fromF = acField("出发城市", r.from_city, ensureCities,
      function () { return S.cities; },
      function (v) { r.from_city = v; refreshTitle(); });
    var toF = acField("到达城市", r.to_city, ensureCities,
      function () { return S.cities; },
      function (v) { r.to_city = v; refreshTitle(); });
    var swap = el("button", "swap-btn", "⇄");
    swap.title = "互换出发/到达";
    swap.addEventListener("click", function () {
      var tmp = r.from_city;
      r.from_city = r.to_city;
      r.to_city = tmp;
      fromF.input.value = r.from_city;
      toF.input.value = r.to_city;
      refreshTitle();
    });
    line.appendChild(fromF.root);
    line.appendChild(swap);
    line.appendChild(toF.root);
    card.appendChild(line);

    var grid = el("div", "form-grid");
    var lb1 = el("label", null, "查询窗口(天)");
    var inWd = el("input");
    inWd.type = "number";
    inWd.value = r.window_days;
    inWd.addEventListener("input", function () {
      var v = parseInt(inWd.value, 10);
      if (!isNaN(v)) r.window_days = v;
    });
    lb1.appendChild(inWd);
    grid.appendChild(lb1);

    var lb2 = el("label", null, "心理价位·含税总价(元)");
    var inTh = el("input");
    inTh.type = "number";
    inTh.value = r.threshold_total;
    inTh.addEventListener("input", function () {
      var v = parseFloat(inTh.value);
      if (!isNaN(v)) r.threshold_total = v;
    });
    lb2.appendChild(inTh);
    var chips = el("div", "quick-chips");
    [300, 400, 500, 600].forEach(function (v) {
      var c = el("button", "chip-btn", "¥" + v);
      c.type = "button";
      c.addEventListener("click", function () {
        r.threshold_total = v;
        inTh.value = v;
      });
      chips.appendChild(c);
    });
    lb2.appendChild(chips);
    grid.appendChild(lb2);
    card.appendChild(grid);

    var tc = r.train_compare || { enabled: true, station_pairs: [] };
    r.train_compare = tc;
    if (!tc.station_pairs) tc.station_pairs = [];

    var sec = el("div", "pair-section");
    var phead = el("div", "pair-head");
    phead.appendChild(el("span", null, "🚄 列车对比 (12306·全席位)"));
    var ck = el("label", "check");
    var cb = el("input");
    cb.type = "checkbox";
    cb.checked = tc.enabled !== false;
    cb.addEventListener("change", function () { tc.enabled = cb.checked; });
    ck.appendChild(cb);
    ck.appendChild(document.createTextNode("启用"));
    phead.appendChild(ck);
    sec.appendChild(phead);
    sec.appendChild(el("div", "muted pair-hint",
      "车站从12306车站库联想选择(中文/拼音均可, 如 hzd→杭州东); 选择即精确匹配, 不会因手输偏差走模糊搜索"));

    var pairsBox = el("div");
    sec.appendChild(pairsBox);

    function renderPairs() {
      pairsBox.textContent = "";
      ensureStations().catch(function () {});
      (tc.station_pairs || []).forEach(function (pair, pi) {
        var row = el("div", "pair-row");
        var f1 = acField("出发站", pair[0], ensureStations,
          function () { return S.stations; },
          function (v) { pair[0] = v; }, "如 杭州东 / hzd");
        var f2 = acField("到达站", pair[1], ensureStations,
          function () { return S.stations; },
          function (v) { pair[1] = v; }, "如 重庆北 / cqb");
        var rm = el("button", "btn danger small", "×");
        rm.type = "button";
        rm.title = "删除该车站对";
        rm.addEventListener("click", function () {
          tc.station_pairs.splice(pi, 1);
          renderPairs();
        });
        row.appendChild(f1.root);
        row.appendChild(el("span", "pair-arrow", "→"));
        row.appendChild(f2.root);
        row.appendChild(rm);
        pairsBox.appendChild(row);
      });
      var add = el("button", "btn small", "+ 添加车站对");
      add.type = "button";
      add.addEventListener("click", function () {
        tc.station_pairs.push(["", ""]);
        renderPairs();
      });
      pairsBox.appendChild(add);
    }
    renderPairs();
    card.appendChild(sec);
    return card;
  }

  /* ---------- 数据源 / 设置 ---------- */

  function renderSources() {
    if (!S.cfg || !S.sources) return;
    var box = $("sourcesList");
    box.textContent = "";
    Object.keys(S.sources).forEach(function (key) {
      var src = S.sources[key];
      var row = el("div", "src-row");
      var cb = el("input");
      cb.type = "checkbox";
      cb.checked = !!(S.cfg.sources && S.cfg.sources.enabled && S.cfg.sources.enabled[key]);
      if (src.status !== "可用") cb.disabled = true;
      cb.addEventListener("change", function () {
        S.cfg.sources.enabled[key] = cb.checked;
      });
      row.appendChild(cb);
      row.appendChild(el("span", "s-name", src.name));
      row.appendChild(el("span", "chip " + (src.status === "可用" ? "ok" : "plan"), src.status));
      row.appendChild(el("span", "s-desc", src.desc));
      box.appendChild(row);
    });
    $("taxAirport").value = S.cfg.tax.airport_fee;
    $("taxFuel").value = S.cfg.tax.fuel_surcharge;
    $("taxIncluded").checked = !!S.cfg.tax.calendar_price_includes_tax;
    $("schInterval").value = S.cfg.schedule.interval_minutes;
    $("schJitter").value = S.cfg.schedule.jitter_minutes;
    $("webHost").value = S.cfg.webui.host;
    $("webPort").value = S.cfg.webui.port;

    $("taxAirport").oninput = function () { S.cfg.tax.airport_fee = parseFloat(this.value) || 0; };
    $("taxFuel").oninput = function () { S.cfg.tax.fuel_surcharge = parseFloat(this.value) || 0; };
    $("taxIncluded").onchange = function () { S.cfg.tax.calendar_price_includes_tax = this.checked; };
    $("schInterval").oninput = function () { S.cfg.schedule.interval_minutes = parseInt(this.value, 10) || 45; };
    $("schJitter").oninput = function () { S.cfg.schedule.jitter_minutes = parseInt(this.value, 10) || 0; };
    $("webHost").oninput = function () { S.cfg.webui.host = this.value.trim() || "127.0.0.1"; };
    $("webPort").oninput = function () { S.cfg.webui.port = parseInt(this.value, 10) || 8765; };
  }

  function renderPush() {
    if (!S.cfg) return;
    $("barkKey").value = S.cfg.push.bark_key || "";
    $("scKey").value = S.cfg.push.serverchan_sendkey || "";
    $("pushGroup").value = S.cfg.push.group || "";
    $("pushSound").value = S.cfg.push.sound || "";
    $("barkKey").oninput = function () { S.cfg.push.bark_key = this.value.trim(); };
    $("scKey").oninput = function () { S.cfg.push.serverchan_sendkey = this.value.trim(); };
    $("pushGroup").oninput = function () { S.cfg.push.group = this.value; };
    $("pushSound").oninput = function () { S.cfg.push.sound = this.value.trim(); };
  }

  function applyConfigResp(resp) {
    S.cfg = resp.config;
    S.secrets = resp.secrets_set;
    S.sources = resp.sources || S.sources;
    renderRoutesEditor();
    renderSources();
    renderPush();
  }

  function cleanCfgForSave() {
    var c = JSON.parse(JSON.stringify(S.cfg));
    for (var i = 0; i < c.routes.length; i++) {
      var r = c.routes[i];
      r.from_city = (r.from_city || "").trim();
      r.to_city = (r.to_city || "").trim();
      if (!r.from_city || !r.to_city) {
        throw new Error("线路 " + (i + 1) + " 的出发/到达城市未填写");
      }
      var tc = r.train_compare || {};
      tc.station_pairs = (tc.station_pairs || []).filter(function (p) {
        return (p[0] || "").trim() && (p[1] || "").trim();
      });
      r.train_compare = tc;
    }
    return c;
  }

  function saveConfig() {
    var payload;
    try {
      payload = cleanCfgForSave();
    } catch (e) {
      toast("保存失败: " + e.message);
      return;
    }
    post("/api/config", payload).then(function (resp) {
      applyConfigResp(resp);
      toast("已保存 ✓ (查询类设置下次查询生效)");
    }).catch(function (e) { toast("保存失败: " + e.message); });
  }

  /* ---------- 提醒历史 / 日志 ---------- */

  function loadAlerts() {
    api("/api/alerts").then(function (resp) {
      var box = $("alertsList");
      box.textContent = "";
      if (!resp.alerts.length) {
        box.appendChild(el("div", "muted", "暂无提醒记录 (低于心理价位时才会推送)"));
        return;
      }
      resp.alerts.forEach(function (a) {
        var item = el("div", "alert-item");
        item.appendChild(el("div", "a-title", a.title));
        item.appendChild(el("div", "a-meta", a.ts.replace("T", " ") + (a.route ? " · " + a.route : "")));
        var body = el("div", "a-body", a.body);
        item.appendChild(body);
        if (a.url) {
          var l = el("a", null, "购票链接 →");
          l.href = a.url;
          l.target = "_blank";
          item.appendChild(l);
        }
        box.appendChild(item);
      });
    }).catch(function () {});
  }

  function loadLog() {
    api("/api/log").then(function (resp) {
      $("logBox").textContent = resp.log || "(空)";
    }).catch(function () {});
  }

  /* ---------- 爬虫监控 ---------- */

  var SRC_NAMES = {
    "qunar-calendar": "去哪儿·低价日历",
    "12306-train": "12306·车票查询",
    "push": "提醒推送"
  };

  function fmtMs(ms) {
    if (ms == null) return "--";
    return ms < 1000 ? ms + "ms" : (ms / 1000).toFixed(1) + "s";
  }

  function crawlStepRow(st) {
    var row = el("div", "crawl-step");
    row.appendChild(el("span", "dot " + (st.status || "ok")));
    row.appendChild(el("span", "crawl-src", SRC_NAMES[st.source] || st.source));
    row.appendChild(el("span", null, st.action || st.label || ""));
    if (st.label && st.action) row.appendChild(el("span", "muted", st.label));
    if (st.cached) row.appendChild(el("span", "chip plan", "缓存命中"));
    if (st.count) row.appendChild(el("span", null, st.count + " 条"));
    if (st.error) row.appendChild(el("span", "crawl-err", st.error));
    row.appendChild(el("span", "crawl-ms", fmtMs(st.ms)));
    return row;
  }

  function crawlRunCard(run, live) {
    var running = !run.finished_at;
    var card = el("div", "crawl-run" + (running ? " run-now" : ""));
    var head = el("div", "crawl-head");
    head.appendChild(el("span", "chip " + (running ? "plan" : (run.ok ? "ok" : "err")),
      running ? "抓取中…" : (run.ok ? "完成" : "有错误")));
    head.appendChild(el("span", "muted", String(run.started_at || "").replace("T", " ")));
    head.appendChild(el("span", "chip plan", run.trigger === "manual" ? "手动" : "计划"));
    var s = run.summary || {};
    var bits = [];
    if (s.routes != null) bits.push("线路 " + s.routes);
    if (s.deals != null) bits.push("报价 " + s.deals + " 条");
    if (s.days_below != null) bits.push("低于价位 " + s.days_below + " 天");
    if (s.pushed) bits.push("已推送");
    if (bits.length) head.appendChild(el("span", "muted", bits.join(" · ")));
    if (!running && run.duration_ms != null) head.appendChild(el("span", "muted", "耗时 " + fmtMs(run.duration_ms)));
    if (running) head.appendChild(el("span", "live-dot"));
    card.appendChild(head);
    var steps = el("div", "crawl-steps");
    (run.steps || []).forEach(function (st) { steps.appendChild(crawlStepRow(st)); });
    if (!(run.steps || []).length) steps.appendChild(el("div", "muted", "暂无步骤记录"));
    card.appendChild(steps);
    return card;
  }

  function renderCrawl(doc) {
    var box = $("crawlPanel");
    box.textContent = "";
    var runs = [];
    if (doc && doc.current) runs.push(doc.current);
    if (doc && doc.history) runs = runs.concat(doc.history);
    if (!runs.length) {
      box.appendChild(el("div", "muted", "暂无抓取记录: 点击「立即查询」跑一次, 或等计划任务触发后刷新"));
      return;
    }
    runs.forEach(function (run, i) { box.appendChild(crawlRunCard(run, i === 0)); });
  }

  function loadCrawl() {
    api("/api/crawl-status").then(renderCrawl).catch(function () {});
  }

  var crawlTimer = null;
  function startCrawlPolling() {
    stopCrawlPolling();
    crawlTimer = setInterval(loadCrawl, 2000);
  }
  function stopCrawlPolling() {
    if (crawlTimer) { clearInterval(crawlTimer); crawlTimer = null; }
  }

  /* ---------- 事件绑定 ---------- */

  function bindTabs() {
    var btns = document.querySelectorAll("#mainTabs button");
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        btns.forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active");
        document.querySelectorAll(".tab-panel").forEach(function (p) { p.classList.remove("active"); });
        $("tab-" + b.dataset.tab).classList.add("active");
        if (b.dataset.tab === "push") loadAlerts();
        if (b.dataset.tab === "logs") loadLog();
        if (b.dataset.tab === "crawl") loadCrawl();
      });
    });
  }

  function bindActions() {
    $("btnRun").addEventListener("click", function () {
      var btn = $("btnRun");
      btn.disabled = true;
      btn.textContent = "查询中(5-20秒)…";
      startCrawlPolling();
      post("/api/run", { push: true }).then(function (resp) {
        S.snap = resp.snapshot;
        S.routeId = S.snap.routes && S.snap.routes.length ? (curRoute() || S.snap.routes[0]).id : null;
        renderRouteTabs();
        renderDash();
        toast("查询完成 ✓");
      }).catch(function (e) {
        toast("查询失败: " + e.message);
      }).finally(function () {
        stopCrawlPolling();
        loadCrawl();
        btn.disabled = false;
        btn.textContent = "立即查询";
      });
    });

    $("btnAddRoute").addEventListener("click", function () {
      S.cfg.routes.push({
        id: "r" + Date.now().toString(36),
        from_city: "",
        to_city: "",
        window_days: 60,
        threshold_total: 500,
        train_compare: { enabled: true, station_pairs: [] }
      });
      renderRoutesEditor();
    });
    $("btnSaveRoutes").addEventListener("click", saveConfig);
    $("btnSaveSources").addEventListener("click", saveConfig);
    $("btnSavePush").addEventListener("click", saveConfig);
    $("btnTestPush").addEventListener("click", function () {
      var btn = $("btnTestPush");
      btn.disabled = true;
      post("/api/test-push").then(function (resp) {
        toast("已发送: " + resp.results.join(", "));
      }).catch(function (e) {
        toast("发送失败: " + e.message);
      }).finally(function () { btn.disabled = false; });
    });
    $("btnRefreshLog").addEventListener("click", loadLog);
    $("btnRefreshCrawl").addEventListener("click", loadCrawl);
  }

  function init() {
    bindTabs();
    bindActions();
    Promise.all([api("/api/config"), api("/api/snapshot")]).then(function (rs) {
      applyConfigResp(rs[0]);
      S.snap = rs[1].snapshot;
      if (S.snap && S.snap.routes && S.snap.routes.length) S.routeId = S.snap.routes[0].id;
      renderRouteTabs();
      renderDash();
    }).catch(function (e) {
      toast("初始化失败: " + e.message);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
