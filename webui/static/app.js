"use strict";
(function () {
  var S = {
    cfg: null, secrets: null, sources: null,
    snap: null, routeId: null, selDate: null
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
      items.forEach(function (it) { it.pair = pair; out.push(it); });
    });
    return { fares: out, errors: errors };
  }

  function cheapestFlight(route) {
    var ds = (route && route.deals) || [];
    if (!ds.length) return null;
    var best = ds[0];
    for (var i = 1; i < ds.length; i++) if (ds[i].total_price < best.total_price) best = ds[i];
    return best;
  }

  function cheapestTrain(route) {
    var t = collectTrains(route);
    var best = null;
    t.fares.forEach(function (f) {
      if (f.second_class && (!best || f.second_class < best.second_class)) best = f;
    });
    return { best: best, all: t.fares, errors: t.errors };
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
    var tr = cheapestTrain(route);
    var items = [];
    items.push({
      label: "最低机票总价", value: fmtMoney(f.total_price),
      sub: f.date + " " + weekday(f.date) + " · " + f.flight_no,
      cls: f.total_price < route.threshold_total ? "good" : ""
    });
    items.push({
      label: "低于心理价位", value: route.days_below + " 天",
      sub: "窗口 " + route.window[0] + " ~ " + route.window[1],
      cls: route.days_below > 0 ? "good" : "warn"
    });
    items.push({ label: "心理价位(含税)", value: fmtMoney(route.threshold_total), sub: "低于即推送提醒" });
    if (tr.best) {
      items.push({
        label: "动车二等最低", value: fmtMoney(tr.best.second_class),
        sub: tr.best.train_code + " · 历时" + tr.best.duration_text
      });
      items.push({
        label: "学生动车 ≈", value: fmtMoney(tr.best.second_class * 0.75),
        sub: "二等座公布价75折估算", cls: "good"
      });
    }
    items.forEach(function (it) {
      var k = el("div", "kpi" + (it.cls ? " " + it.cls : ""));
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
    var tr = cheapestTrain(route);
    var t = tr.best;
    var s = t ? t.second_class * 0.75 : null;

    var winner, save = null;
    if (s && s <= f.total_price) { winner = "student"; save = f.total_price - s; }
    else if (t && t.second_class <= f.total_price) { winner = "train"; save = f.total_price - t.second_class; }
    else if (t) { winner = "flight"; save = t.second_class - f.total_price; }
    else { winner = "flight"; }

    var names = { student: "学生动车", train: "动车二等座", flight: "机票" };
    var banner = el("div", "verdict-banner");
    var b = el("b", null, "当前最优: " + names[winner]);
    banner.appendChild(b);
    banner.appendChild(document.createTextNode(
      (save != null ? " , 比次优方案最多可省约 " + fmtMoney(save) : "") +
      "。时间成本参考: 飞机航程约2.5小时(含提前值机全程约4-5小时), 动车历时8-15小时; 夕发朝至动车可在车上过夜, 省一晚住宿。"));
    box.appendChild(banner);

    var cards = el("div", "verdict-cards");
    function vcard(kind, isBest, title, price, sub) {
      var c = el("div", "vcard" + (isBest ? " best" : ""));
      if (isBest) c.appendChild(el("div", "v-tag", "最优"));
      c.appendChild(el("div", "v-title", title));
      c.appendChild(el("div", "v-price", price));
      var sd = el("div", "v-sub");
      sd.innerHTML = sub;
      c.appendChild(sd);
      return c;
    }
    cards.appendChild(vcard("flight", winner === "flight",
      "✈️ 最低机票 (" + f.date + ")", fmtMoney(f.total_price),
      esc(f.flight_no + " " + f.airline) + " · 裸价" + fmtMoney(f.bare_price) + "+税费<br>" +
      "行李: " + esc(f.baggage) + " · <a href=\"" + esc(f.url) + "\" target=\"_blank\">去下单</a>"));
    if (t) {
      cards.appendChild(vcard("train", winner === "train",
        "🚄 动车二等 (" + t.train_code + ")", fmtMoney(t.second_class),
        esc(t.pair.replace("-", " → ")) + " · " + esc(t.dep_time) + "-" + esc(t.arr_time) +
        " 历时" + esc(t.duration_text)));
      cards.appendChild(vcard("student", winner === "student",
        "🎓 学生动车 ≈", fmtMoney(s),
        "二等座公布票价75折估算<br>资格/优惠区间以12306下单页为准"));
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
    var tr = cheapestTrain(route);
    if (tr.best) {
      var ref = el("div", "muted");
      ref.textContent = "参考: " + tr.best.train_code + " 动车二等 " + fmtMoney(tr.best.second_class) +
        " / 学生动车≈" + fmtMoney(tr.best.second_class * 0.75) +
        " (" + tr.best.pair.replace("-", "→") + " " + tr.best.dep_time + "出发)";
      box.appendChild(ref);
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
      box.appendChild(el("div", "muted", "未启用动车对比或暂无数据(可在数据源/线路管理中开启)"));
      return;
    }
    $("trainMeta").textContent = "查询日 " + route.train.query_date + " · 更新于 " + String(route.train.updated_at || "").replace("T", " ");
    var tr = cheapestTrain(route);
    tr.errors.forEach(function (e) {
      box.appendChild(el("div", "err-line", "⚠️ " + e));
    });
    if (!tr.all.length) {
      box.appendChild(el("div", "muted", "未查到车次"));
      return;
    }
    var sorted = tr.all.slice().sort(function (a, b) { return (a.second_class || 9e9) - (b.second_class || 9e9); });
    var wrap = el("div", "tbl-scroll");
    var tb = el("table", "tbl");
    tb.innerHTML = "<tr><th>车次</th><th>区间</th><th>时刻</th><th>历时</th><th>二等座</th><th>学生≈</th></tr>";
    var minP = tr.best ? tr.best.second_class : null;
    sorted.slice(0, 20).forEach(function (t) {
      var row = el("tr", (t.second_class && t.second_class === minP) ? "low" : "");
      function td(v) { var d = el("td"); d.textContent = v == null ? "--" : v; return d; }
      row.appendChild(td(t.train_code));
      row.appendChild(td(t.pair.replace("-", " → ")));
      row.appendChild(td(t.dep_time + " - " + t.arr_time));
      row.appendChild(td(t.duration_text));
      row.appendChild(t.second_class ? td(fmtMoney(t.second_class)) : td("--"));
      row.appendChild(t.second_class ? td(fmtMoney(t.second_class * 0.75)) : td("--"));
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
    note.textContent = "学生票=动车组二等座公布票价×75%(估算值,以12306下单页为准)" +
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

  function renderRoutesEditor() {
    var box = $("routesEditor");
    box.textContent = "";
    if (!S.cfg) return;
    S.cfg.routes.forEach(function (r, idx) {
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

      var grid = el("div", "form-grid");
      function fld(labelText, value, type, field) {
        var lb = el("label", null, labelText);
        var input = el("input");
        input.type = type;
        input.value = value;
        input.addEventListener("input", function () {
          var v = type === "number" ? parseFloat(input.value) : input.value;
          if (type === "number" && isNaN(v)) return;
          r[field] = v;
          if (field === "from_city" || field === "to_city") title.textContent = r.from_city + " → " + r.to_city;
        });
        lb.appendChild(input);
        return lb;
      }
      grid.appendChild(fld("出发城市(中文)", r.from_city, "text", "from_city"));
      grid.appendChild(fld("到达城市(中文)", r.to_city, "text", "to_city"));
      grid.appendChild(fld("查询窗口(天)", r.window_days, "number", "window_days"));
      grid.appendChild(fld("心理价位·总价(元)", r.threshold_total, "number", "threshold_total"));
      card.appendChild(grid);

      var tc = r.train_compare || { enabled: true, station_pairs: [] };
      r.train_compare = tc;
      var pe = el("div", "pair-edit");
      var lbl = el("label", null, "动车对比车站对 (每行: 出发站|到达站, 如 杭州东|重庆北)");
      var ta = el("textarea");
      ta.value = (tc.station_pairs || []).map(function (p) { return p.join("|"); }).join("\n");
      ta.addEventListener("input", function () {
        tc.station_pairs = ta.value.split(/\r?\n/).map(function (line) {
          return line.split("|").map(function (x) { return x.trim(); }).filter(Boolean);
        }).filter(function (p) { return p.length === 2; });
      });
      lbl.appendChild(ta);
      pe.appendChild(lbl);
      var ck = el("label", "check");
      var cb = el("input");
      cb.type = "checkbox";
      cb.checked = tc.enabled !== false;
      cb.addEventListener("change", function () { tc.enabled = cb.checked; });
      ck.appendChild(cb);
      ck.appendChild(document.createTextNode(" 启用12306动车对比"));
      pe.appendChild(ck);
      card.appendChild(pe);
      box.appendChild(card);
    });
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

  function saveConfig() {
    return post("/api/config", S.cfg).then(function (resp) {
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
      });
    });
  }

  function bindActions() {
    $("btnRun").addEventListener("click", function () {
      var btn = $("btnRun");
      btn.disabled = true;
      btn.textContent = "查询中(5-20秒)…";
      post("/api/run", { push: true }).then(function (resp) {
        S.snap = resp.snapshot;
        S.routeId = S.snap.routes && S.snap.routes.length ? (curRoute() || S.snap.routes[0]).id : null;
        renderRouteTabs();
        renderDash();
        toast("查询完成 ✓");
      }).catch(function (e) {
        toast("查询失败: " + e.message);
      }).finally(function () {
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
        train_compare: { enabled: true, station_pairs: [["杭州东", "重庆北"]] }
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

