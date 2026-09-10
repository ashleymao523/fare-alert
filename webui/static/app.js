"use strict";
(function () {
  var S = {
    cfg: null, secrets: null, sources: null,
    snap: null, routeId: null, selDate: null,
    calView: "cal",
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
    var ds = ((route && route.deals) || []).filter(function (d) {
      return d.source !== "nearby-ref" && d.source !== "interp";
    });
    if (!ds.length) return null;
    var best = ds[0];
    for (var i = 1; i < ds.length; i++) if (ds[i].total_price < best.total_price) best = ds[i];
    return best;
  }

  /* ---------- v0.8 城市图鉴 & 路线 Hero ---------- */

  var CITY_INFO = {
    "杭州": { en: "Hangzhou", emoji: "🌊", desc: "西湖烟雨 · 数字之城", g: "cg1" },
    "重庆": { en: "Chongqing", emoji: "🌶", desc: "8D魔幻山城 · 火锅之都", g: "cg2" },
    "成都": { en: "Chengdu", emoji: "🐼", desc: "天府之国 · 悠闲慢生活", g: "cg3" },
    "北京": { en: "Beijing", emoji: "🏯", desc: "千年古都 · 红墙金瓦", g: "cg4" },
    "上海": { en: "Shanghai", emoji: "🌃", desc: "魔都 · 外滩万国建筑", g: "cg5" },
    "西安": { en: "Xi'an", emoji: "🏺", desc: "十三朝古都 · 兵马俑", g: "cg6" },
    "广州": { en: "Guangzhou", emoji: "🍜", desc: "食在广州 · 早茶之城", g: "cg7" },
    "深圳": { en: "Shenzhen", emoji: "🌆", desc: "青春之城 · 科技硅谷", g: "cg8" },
    "昆明": { en: "Kunming", emoji: "🌸", desc: "春城 · 四季花开", g: "cg1" },
    "厦门": { en: "Xiamen", emoji: "🏝", desc: "海上花园 · 鼓浪屿", g: "cg2" },
    "三亚": { en: "Sanya", emoji: "🏖", desc: "东方夏威夷 · 椰风海韵", g: "cg3" },
    "海口": { en: "Haikou", emoji: "🥥", desc: "椰城 · 骑楼老街", g: "cg4" },
    "丽江": { en: "Lijiang", emoji: "🏔", desc: "艳遇之都 · 古城雪山", g: "cg5" },
    "大理": { en: "Dali", emoji: "🌾", desc: "风花雪月 · 苍山洱海", g: "cg6" },
    "长沙": { en: "Changsha", emoji: "🔥", desc: "星城 · 网红美食", g: "cg7" },
    "武汉": { en: "Wuhan", emoji: "🌸", desc: "江城 · 樱花黄鹤楼", g: "cg8" },
    "南京": { en: "Nanjing", emoji: "🗿", desc: "六朝古都 · 秦淮风月", g: "cg1" },
    "青岛": { en: "Qingdao", emoji: "🍺", desc: "红瓦绿树 · 碧海蓝天", g: "cg2" },
    "哈尔滨": { en: "Harbin", emoji: "❄️", desc: "冰城 · 东方莫斯科", g: "cg5" },
    "沈阳": { en: "Shenyang", emoji: "🏛", desc: "盛京 · 一朝发祥地", g: "cg6" },
    "郑州": { en: "Zhengzhou", emoji: "⚒", desc: "中原枢纽 · 商都", g: "cg7" },
    "洛阳": { en: "Luoyang", emoji: "🌺", desc: "牡丹花城 · 龙门石窟", g: "cg8" },
    "天津": { en: "Tianjin", emoji: "🎡", desc: "津门 · 曲艺之乡", g: "cg1" },
    "贵阳": { en: "Guiyang", emoji: "⛰", desc: "林城 · 避暑之都", g: "cg2" },
    "桂林": { en: "Guilin", emoji: "🛶", desc: "山水甲天下", g: "cg3" },
    "南宁": { en: "Nanning", emoji: "🌿", desc: "绿城 · 壮乡首府", g: "cg4" },
    "福州": { en: "Fuzhou", emoji: "🌴", desc: "榕城 · 有福之州", g: "cg5" },
    "济南": { en: "Jinan", emoji: "⛲", desc: "泉城 · 四面荷花", g: "cg6" },
    "兰州": { en: "Lanzhou", emoji: "🐂", desc: "金城 · 黄河穿城", g: "cg7" },
    "乌鲁木齐": { en: "Ürümqi", emoji: "🏔", desc: "亚洲腹地 · 丝路枢纽", g: "cg8" },
    "拉萨": { en: "Lhasa", emoji: "🕌", desc: "日光城 · 高原圣域", g: "cg5" },
    "西宁": { en: "Xining", emoji: "🌊", desc: "夏都 · 青海门户", g: "cg6" },
    "香港": { en: "Hong Kong", emoji: "🏙", desc: "东方之珠 · 购物天堂", g: "cg7" },
    "澳门": { en: "Macau", emoji: "🎰", desc: "东方蒙特卡洛", g: "cg8" },
    "台北": { en: "Taipei", emoji: "🏮", desc: "夜市之都 · 101大厦", g: "cg1" },
    "曼谷": { en: "Bangkok", emoji: "🛕", desc: "天使之城 · 街头美食", g: "cg2" },
    "清迈": { en: "Chiang Mai", emoji: "🌿", desc: "泰北玫瑰 · 慢城", g: "cg3" },
    "普吉": { en: "Phuket", emoji: "🏝", desc: "安达曼海上明珠", g: "cg4" },
    "东京": { en: "Tokyo", emoji: "🗼", desc: "霓虹都市 · 樱花动漫", g: "cg5" },
    "大阪": { en: "Osaka", emoji: "🍣", desc: "天下厨房 · 环球影城", g: "cg6" },
    "首尔": { en: "Seoul", emoji: "🏙", desc: "韩流之都 · 明洞购物", g: "cg7" },
    "新加坡": { en: "Singapore", emoji: "🦁", desc: "狮城 · 花园城市", g: "cg8" },
    "吉隆坡": { en: "Kuala Lumpur", emoji: "🗼", desc: "双子塔 · 美食熔炉", g: "cg1" },
    "巴厘岛": { en: "Bali", emoji: "🌴", desc: "众神之岛 · 度假天堂", g: "cg2" }
  };

  function cityInfo(name) {
    return CITY_INFO[name] ||
      { en: "", emoji: "📍", desc: "低价好去处 · 点击直达查票", g: "cg0" };
  }

  // offline "travel poster" silhouettes per city scene type
  var CITY_SCENES = {
    "杭州": "lake", "西宁": "lake", "大理": "lake", "武汉": "skyline",
    "重庆": "skyline", "上海": "skyline", "深圳": "skyline", "广州": "skyline",
    "香港": "skyline", "台北": "skyline", "首尔": "skyline", "新加坡": "skyline",
    "天津": "skyline", "沈阳": "skyline", "贵阳": "skyline", "南宁": "skyline",
    "福州": "skyline", "济南": "skyline", "长沙": "skyline",
    "北京": "temple", "西安": "temple", "南京": "temple", "洛阳": "temple",
    "郑州": "temple", "澳门": "temple",
    "三亚": "beach", "海口": "beach", "厦门": "beach", "普吉": "beach",
    "巴厘岛": "beach",
    "丽江": "mountain", "昆明": "mountain", "桂林": "mountain",
    "乌鲁木齐": "mountain", "拉萨": "mountain", "兰州": "mountain",
    "东京": "towers", "大阪": "towers", "哈尔滨": "towers", "曼谷": "towers",
    "清迈": "towers", "青岛": "towers", "吉隆坡": "towers"
  };

  var INK = "rgba(8,14,24,0.38)", LIGHT = "rgba(255,255,255,0.30)";

  function citySceneSvg(type) {
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 220 80");
    svg.setAttribute("preserveAspectRatio", "xMidYMax slice");
    function path(d, fill) {
      var p = document.createElementNS("http://www.w3.org/2000/svg", "path");
      p.setAttribute("d", d); p.setAttribute("fill", fill || INK);
      svg.appendChild(p); return p;
    }
    function circle(cx, cy, r, fill) {
      var c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("cx", cx); c.setAttribute("cy", cy); c.setAttribute("r", r);
      c.setAttribute("fill", fill || LIGHT);
      svg.appendChild(c); return c;
    }
    if (type === "lake") {
      circle(178, 20, 9);
      path("M0,64 Q40,36 85,62 Q120,40 150,60 Q185,42 220,64 L220,80 L0,80 Z");
      path("M152,64 L160,44 L168,64 Z");
      path("M150,64 H170 L168,68 H154 Z");
      path("M24,72 q8,-3 16,0 t16,0 t16,0", "none");
      svg.lastChild.setAttribute("stroke", "rgba(255,255,255,0.35)");
      svg.lastChild.setAttribute("stroke-width", "1.6");
      svg.lastChild.setAttribute("fill", "none");
    } else if (type === "skyline") {
      circle(30, 18, 8);
      [[8,14,34],[26,10,50],[40,16,26],[60,12,58],[76,9,40],[88,13,30],
       [106,11,66],[121,8,48],[133,12,36],[150,10,54],[164,14,28],
       [180,9,44],[193,12,60],[208,10,32]].forEach(function (b) {
        path("M" + b[0] + ",80 V" + (80 - b[2]) + " h" + b[1] + " V80 Z");
      });
      path("M111,14 V4 M117,14 V6", "none");
      svg.lastChild.setAttribute("stroke", INK);
      svg.lastChild.setAttribute("stroke-width", "2");
    } else if (type === "temple") {
      circle(178, 20, 9);
      path("M52,42 Q100,20 148,42 L134,47 H66 Z");
      path("M62,56 Q100,40 138,56 L126,60 H74 Z");
      path("M84,47 h32 v9 H84 Z");
      path("M60,66 h80 v5 H60 Z");
      path("M54,73 h92 v7 H54 Z");
      path("M96,30 h8 v-8 h-8 Z");
    } else if (type === "beach") {
      circle(48, 20, 11, "rgba(255,214,140,0.55)");
      path("M168,80 Q163,58 172,42", "none");
      svg.lastChild.setAttribute("stroke", INK);
      svg.lastChild.setAttribute("stroke-width", "4");
      svg.lastChild.setAttribute("fill", "none");
      svg.lastChild.setAttribute("stroke-linecap", "round");
      [[172,42,-20,-10],[172,42,-6,-16],[172,42,10,-14],[172,42,20,-4],[172,42,-16,2]]
        .forEach(function (f) {
          path("M" + f[0] + "," + f[1] + " q" + f[2] + "," + f[3] + " " +
               (f[2] * 2) + "," + (f[3] + 2), "none");
          svg.lastChild.setAttribute("stroke", INK);
          svg.lastChild.setAttribute("stroke-width", "3");
          svg.lastChild.setAttribute("fill", "none");
          svg.lastChild.setAttribute("stroke-linecap", "round");
        });
      path("M0,70 q14,-5 28,0 t28,0 t28,0 t28,0 t28,0 t28,0 t28,0 L220,80 H0 Z",
           "rgba(8,14,24,0.22)");
    } else if (type === "mountain") {
      circle(176, 18, 8);
      path("M0,80 L44,30 L66,52 L98,18 L138,62 L162,38 L220,80 Z");
      path("M92,26 L98,18 L104,26 L100,29 L96,29 Z", "rgba(255,255,255,0.5)");
      path("M39,37 L44,30 L49,37 L46,39 L42,39 Z", "rgba(255,255,255,0.5)");
    } else {  // towers
      circle(40, 18, 8);
      path("M78,80 V30 L88,18 L98,30 V80 Z");
      path("M122,80 V30 L132,18 L142,30 V80 Z");
      path("M92,48 h26 v5 H92 Z");
      path("M86,26 L88,18 L90,26 Z");
      path("M130,26 L132,18 L134,26 Z");
      path("M60,80 h100 v4 H60 Z", "rgba(8,14,24,0.22)");
    }
    return svg;
  }

  var CITY_PHOTOS = {};  // name -> {ok, photo} memory cache per session

  function loadCityPhoto(name, card) {
    if (CITY_PHOTOS[name] !== undefined) {
      applyCityPhoto(card, CITY_PHOTOS[name]);
      return;
    }
    fetch("/api/city-photo?name=" + encodeURIComponent(name))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        CITY_PHOTOS[name] = d && d.ok ? d : { ok: false };
        applyCityPhoto(card, CITY_PHOTOS[name]);
      })
      .catch(function () { CITY_PHOTOS[name] = { ok: false }; });
  }

  function applyCityPhoto(card, d) {
    if (!card || !d || !d.ok || !d.photo) return;
    var probe = new Image();
    probe.onload = function () {
      if (!card.isConnected) return;
      var ph = el("div", "cv-photo");
      ph.style.backgroundImage = "url('" + d.photo + "')";
      card.insertBefore(ph, card.firstChild);
      card.classList.add("has-photo");
      card.appendChild(el("div", "cv-src", "图 Wikipedia"));
    };
    probe.src = d.photo;
  }

  function cityCard(name, iata) {
    var info = cityInfo(name);
    var c = el("div", "city-visual " + info.g);
    var scene = el("div", "cv-scene");
    scene.appendChild(citySceneSvg(CITY_SCENES[name] || "skyline"));
    c.appendChild(scene);
    c.appendChild(el("div", "cv-emoji", info.emoji));
    c.appendChild(el("div", "cv-name", name));
    if (info.en) c.appendChild(el("div", "cv-en", info.en + (iata ? " · " + iata : "")));
    c.appendChild(el("div", "cv-desc", info.desc));
    loadCityPhoto(name, c);
    return c;
  }

  function renderHero(route) {
    var box = $("heroBox");
    box.textContent = "";
    if (!route) { box.classList.add("hidden"); return; }
    box.classList.remove("hidden");
    var hero = el("div", "hero");
    var cities = el("div", "hero-cities");
    cities.appendChild(cityCard(route.from_city, route.from_iata));
    var mid = el("div", "hero-mid");
    mid.appendChild(el("div", "hero-plane", route.trip_type === "roundtrip" ? "⇄" : "✈"));
    mid.appendChild(el("div", "hero-dir", route.trip_type === "roundtrip" ? "往返" : (route.intl ? "国际单程" : "单程")));
    cities.appendChild(mid);
    cities.appendChild(cityCard(route.to_city, route.to_iata));
    hero.appendChild(cities);
    var chips = el("div", "hero-chips");
    var chipsDef = [
      ["📅", "未来 " + (route.window_days || 60) + " 天"],
      ["🎯", "心理价位 " + fmtMoney(route.threshold_total)],
      ["💰", "当前最低 " + (route.cheapest_total ? fmtMoney(route.cheapest_total) : "待查")],
      ["🔔", route.days_below + " 天低于阈值"]
    ];
    chipsDef.forEach(function (cd) {
      var chip = el("span", "hero-chip");
      chip.appendChild(el("span", "hc-ico", cd[0]));
      chip.appendChild(document.createTextNode(cd[1]));
      chips.appendChild(chip);
    });
    hero.appendChild(chips);
    box.appendChild(hero);
  }

  /* ---------- v0.8 Skyscanner 式低价条形视图 ---------- */

  function renderBars(route) {
    var box = $("barsBox");
    box.textContent = "";
    if (!route) return;
    var isRT = !!(route.trip_type === "roundtrip" && route.combined_by_date);
    var days = dayList(route);
    var prices = [], map = {};
    (route.deals || []).forEach(function (d) {
      var t = isRT && (route.combined_by_date || {})[d.date]
        ? route.combined_by_date[d.date].total : d.total_price;
      if (!map[d.date] || t < map[d.date].t) map[d.date] = { t: t, d: d };
      prices.push(t);
    });
    prices = prices.filter(function (p) { return p > 0; }).sort(function (a, b) { return a - b; });
    if (!prices.length) return;
    var pmin = prices[0], pmax = prices[prices.length - 1];
    var hint = el("div", "bars-hint",
      "柱越高越便宜 · 绿=低于心理价位 · 斜纹=临近日参考价 · 点击柱看详情");
    box.appendChild(hint);
    var wrap = el("div", "bars-wrap");
    days.forEach(function (ds) {
      var m = map[ds];
      var col = el("div", "bar-col");
      var track = el("div", "bar-track");
      if (m) {
        var ratio = pmax > pmin
          ? 0.25 + 0.75 * (1 - (m.t - pmin) / (pmax - pmin)) : 1;
        var bar = el("div", "bar" +
          (m.t < route.threshold_total ? " cheap" : "") +
          (m.d.source === "nearby-ref" ? " ref" : "") +
          (m.d.source === "interp" ? " interp" : ""));
        bar.style.height = Math.round(ratio * 100) + "%";
        track.appendChild(bar);
        col.title = ds + " " + weekday(ds) + " · " + fmtMoney(m.t) +
          (m.d.source === "nearby-ref"
            ? " (临近日参考" + (m.d.ref_offset ? " · 距" + m.d.ref_offset + "天" : "") + ")"
            : m.d.source === "interp" ? " (两侧真实价插值估算)" : "");
        col.appendChild(el("div", "bar-price",
          (m.d.source === "nearby-ref" || m.d.source === "interp" ? "≈" : "") + fmtMoney(m.t)));
        col.addEventListener("click", function () {
          S.selDate = ds;
          renderCalendar(route);
          renderBars(route);
          renderDayDetail(route);
          var dd = $("dayDetail");
          if (dd && dd.scrollIntoView) dd.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
      }
      col.appendChild(track);
      var wd = parseDate(ds).getDay();
      col.appendChild(el("div", "bar-date" + ((wd === 0 || wd === 6) ? " wk" : ""), fmtMD(ds)));
      if (ds === S.selDate) col.classList.add("selected");
      wrap.appendChild(col);
    });
    box.appendChild(wrap);
  }

  function renderCalendarView(route) {
    var cal = $("calendar"), bars = $("barsBox");
    var showBars = S.calView === "bars";
    cal.classList.toggle("hidden", showBars);
    bars.classList.toggle("hidden", !showBars);
    var bCal = $("btnViewCal"), bBar = $("btnViewBars");
    if (bCal && bBar) {
      bCal.classList.toggle("active", !showBars);
      bBar.classList.toggle("active", showBars);
    }
    if (showBars) renderBars(route); else renderCalendar(route);
  }

  /* ---------- v0.8 移动端低价提醒横幅 ---------- */

  function checkMobileAlerts(route) {
    var banner = $("alertFloat");
    if (!banner || !route || !route.deals) return;
    var key = "farealert_seen_" + route.id;
    var seen = {};
    try { seen = JSON.parse(localStorage.getItem(key) || "{}"); } catch (e) {}
    var fresh = (route.deals || []).filter(function (d) {
      return d.below && d.source !== "nearby-ref" && d.source !== "interp" && !seen[d.date];
    });
    if (!fresh.length) { banner.classList.remove("show"); return; }
    var cheapest = fresh[0];
    for (var i = 1; i < fresh.length; i++) {
      if (fresh[i].total_price < cheapest.total_price) cheapest = fresh[i];
    }
    fresh.forEach(function (d) { seen[d.date] = 1; });
    try { localStorage.setItem(key, JSON.stringify(seen)); } catch (e) {}
    banner.textContent = "";
    var icon = el("span", "af-icon", "🔔");
    var body = el("div", "af-body");
    body.appendChild(el("div", "af-title",
      route.from_city + "→" + route.to_city + " 有 " + fresh.length + " 天低于心理价位"));
    body.appendChild(el("div", "af-sub",
      "最低 " + fmtMoney(cheapest.total_price) + " · " + cheapest.date + " " + weekday(cheapest.date)));
    var btnGo = el("button", "af-btn", "查看");
    btnGo.addEventListener("click", function () {
      S.selDate = cheapest.date;
      renderDash();
      banner.classList.remove("show");
      var dd = $("dayDetail");
      if (dd && dd.scrollIntoView) dd.scrollIntoView({ behavior: "smooth" });
    });
    var btnX = el("button", "af-close", "×");
    btnX.addEventListener("click", function () { banner.classList.remove("show"); });
    banner.appendChild(icon); banner.appendChild(body);
    banner.appendChild(btnGo); banner.appendChild(btnX);
    banner.classList.add("show");
    if (navigator.vibrate) { try { navigator.vibrate([120, 60, 120]); } catch (e) {} }
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      try {
        new Notification("FareAlert 低价提醒", {
          body: route.from_city + "→" + route.to_city + " 最低 " +
            fmtMoney(cheapest.total_price) + " (" + cheapest.date + ")",
          icon: "/static/icon.svg"
        });
      } catch (e) {}
    }
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
    var isRT = !!(route.trip_type === "roundtrip" && route.combined);
    var tr = trainBest(route);
    var items = [];
    items.push({
      label: isRT ? "往返合计最低" : "最低机票总价",
      value: fmtMoney(isRT ? route.combined.total : f.total_price),
      sub: isRT
        ? ("去 " + fmtMD(route.combined.out_date) + " · 返 " + fmtMD(route.combined.ret_date) +
           " · 最优组合(去+返)")
        : (f.date + " " + weekday(f.date) + " · " + (f.flight_no || f.airline) +
           (f.source === "amadeus-fill" ? " · Amadeus补" : "")),
      cls: (isRT ? route.combined.total : f.total_price) < route.threshold_total ? "good" : "",
      url: isRT ? (route.combined.url || f.url) : f.url
    });
    items.push({
      label: "低于心理价位", value: route.days_below + " 天",
      sub: "窗口 " + route.window[0] + " ~ " + route.window[1],
      cls: route.days_below > 0 ? "good" : "warn"
    });
    items.push({
      label: isRT ? "心理价位(往返合计)" : "心理价位(含税)",
      value: fmtMoney(route.threshold_total), sub: "低于即推送提醒"
    });
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
    var isRT = !!(route.trip_type === "roundtrip" && route.combined);
    var cb = route.combined;
    var tr = trainBest(route);
    var t = tr.second;
    var ze = t ? trainSeats(t)["二等座"] : null;
    var s = t ? ze * 0.75 : null;
    var sl = tr.sleeper;

    var names = { flight: "✈️ 机票", train: "🚄 动车二等座", student: "🎓 学生动车", sleeper: "🛏️ 列车卧铺" };
    var flightPrice = isRT ? cb.total : f.total_price;
    var cands = [{ k: "flight", p: flightPrice }];
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
      isRT ? "✈️ 往返最低 (" + fmtMD(cb.out_date) + "→" + fmtMD(cb.ret_date) + ")"
           : "✈️ 最低机票 (" + f.date + ")",
      fmtMoney(flightPrice),
      isRT
        ? "去程 " + esc(cb.out_flight || f.airline) + " ¥" + Math.round(cb.out_total) +
          " + 返程 " + esc(cb.ret_flight || f.airline) + " ¥" + Math.round(cb.ret_total) +
          " = 合计<br>行李: " + esc(f.baggage) + "<br>两段分别下单, 起降时刻以订单页为准"
        : esc((f.flight_no ? f.flight_no + " " : "") + f.airline) + " · 裸价" + fmtMoney(f.bare_price) + "+税费" +
          (f.source === "amadeus-fill" ? ' <span class="badge amber">Amadeus补</span><br>' : "<br>") +
          "行李: " + esc(f.baggage) + "<br>起降时刻/飞行时长以下单页为准"),
      isRT ? (cb.url || f.url) : f.url);
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
    var isRT = !!(route && route.trip_type === "roundtrip" && route.combined_by_date);
    $("calMeta").textContent = route
      ? ((isRT ? "往返模式: 显示往返合计价" : "点击日期看详情") +
         " · 阈值 " + fmtMoney(route.threshold_total))
      : "";
    if (!route) return;
    var map = {};
    (route.deals || []).forEach(function (d) {
      var cd = isRT ? (route.combined_by_date || {})[d.date] : null;
      if (!cd) { map[d.date] = d; return; }
      var cp = {};
      for (var k in d) cp[k] = d[k];
      cp.total_price = cd.total;
      cp.ret_date = cd.ret_date;
      cp.out_total = cd.out_total;
      cp.ret_total = cd.ret_total;
      cp.ret_flight = cd.ret_flight;
      map[d.date] = cp;
    });
    dayList(route).forEach(function (ds) {
      var d = map[ds];
      var cls = "day " + (d ? heatClass(d.total_price, route.threshold_total) : "empty");
      if (d && d.source === "nearby-ref") cls += " ref";
      if (d && d.source === "interp") cls += " interp";
      if (ds === S.selDate) cls += " selected";
      var c = el("div", cls);
      c.appendChild(el("div", "d-date", fmtMD(ds)));
      var wk = el("div", "d-week", weekday(ds));
      var wd = parseDate(ds).getDay();
      if (wd === 0 || wd === 6) wk.classList.add("wk");
      c.appendChild(wk);
      c.appendChild(el("div", "d-price", d
        ? (d.source === "nearby-ref" || d.source === "interp" ? "≈" : "") + fmtMoney(d.total_price)
        : "—"));
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
    var isRT = !!(route.trip_type === "roundtrip" && route.combined_by_date);
    var map = {};
    (route.deals || []).forEach(function (d) {
      var cd = isRT ? (route.combined_by_date || {})[d.date] : null;
      if (!cd) { map[d.date] = d; return; }
      var cp = {};
      for (var k in d) cp[k] = d[k];
      cp.total_price = cd.total;
      cp.ret_date = cd.ret_date;
      cp.out_total = cd.out_total;
      cp.ret_total = cd.ret_total;
      cp.ret_flight = cd.ret_flight;
      map[d.date] = cp;
    });
    var d = map[S.selDate];
    box.classList.remove("hidden");
    if (!d) {
      box.appendChild(el("div", "dd-title", S.selDate + " " + weekday(S.selDate) + " · 该日无报价"));
      return;
    }
    var below = d.total_price < route.threshold_total;
    var title = el("div", "dd-title");
    title.appendChild(document.createTextNode(d.date + " " + weekday(d.date)));
    var priceSpan = el("span");
    priceSpan.innerHTML = "含税 <b style=\"font-variant-numeric:tabular-nums\">" + fmtMoney(d.total_price) + "</b>";
    title.appendChild(priceSpan);
    var badge = el("span", "badge " + (below ? "green" : "gray"),
      below ? "低于心理价位" : "高于心理价位");
    title.appendChild(badge);
    if (d.source === "qunar-intl") {
      title.appendChild(el("span", "badge sky", "国际特价"));
    } else if (d.source === "amadeus-intl") {
      title.appendChild(el("span", "badge sky", "Amadeus"));
    } else if (d.source === "amadeus-fill") {
      title.appendChild(el("span", "badge amber", "Amadeus补"));
    } else if (d.source === "nearby-ref") {
      title.appendChild(el("span", "badge gray",
        d.ref_offset ? "临近日参考 · 距" + d.ref_offset + "天" : "临近日参考"));
    } else if (d.source === "interp") {
      title.appendChild(el("span", "badge amber", "两侧真实价插值"));
    }
    box.appendChild(title);

    // ---- flight timeline: dep &arr times, duration ----
    var hasTime = !!(d.dep_time && d.arr_time);
    var connecting = (d.flight_no || "").indexOf("/") >= 0;
    var tl = el("div", "ft-line");
    var depEnd = el("div", "ft-endpoint");
    depEnd.appendChild(el("div", "ft-time" + (hasTime ? "" : " unknown"), hasTime ? d.dep_time : "--:--"));
    depEnd.appendChild(el("div", "ft-code", route.from_iata || route.from_city || "出发"));
    var mid = el("div", "ft-mid");
    var durBox = el("div");
    durBox.appendChild(el("span", "ft-dur", connecting ? "中转 · " + (d.duration_text || "全程时刻待查") : (d.duration_text || "飞行时长待查")));
    if (!hasTime) durBox.appendChild(el("span", "ft-pend", "时刻待接入"));
    mid.appendChild(durBox);
    var path = el("div", "ft-path");
    path.appendChild(el("span", "ft-plane", "\u2708"));
    mid.appendChild(path);
    var arrEnd = el("div", "ft-endpoint");
    arrEnd.appendChild(el("div", "ft-time" + (hasTime ? "" : " unknown"), hasTime ? d.arr_time : "--:--"));
    arrEnd.appendChild(el("div", "ft-code", route.to_iata || route.to_city || "到达"));
    tl.appendChild(depEnd); tl.appendChild(mid); tl.appendChild(arrEnd);
    box.appendChild(tl);

    var warn = /不含|确认/.test(d.baggage) ? " ⚠️" : " 🧳";
    var line = el("div");
    if (isRT && d.ret_date) {
      line.innerHTML = "去程 " + esc(d.flight_no || d.airline) + " ¥" + Math.round(d.out_total) +
        " + 返程 " + fmtMD(d.ret_date) + " " + esc(d.ret_flight || d.airline) +
        " ¥" + Math.round(d.ret_total) + " = <b>" + fmtMoney(d.total_price) + "</b>" +
        warn + esc(d.baggage) +
        (d.alert ? " · <span class=\"badge green\">已推送提醒</span>" : "");
    } else {
      line.innerHTML = esc((d.flight_no ? d.flight_no + " " : "") + d.airline) + " · 裸价 " + fmtMoney(d.bare_price) +
        " + 机建燃油 = <b>" + fmtMoney(d.total_price) + "</b>" + warn + esc(d.baggage) +
        (d.alert ? " · <span class=\"badge green\">已推送提醒</span>" : "");
    }
    line.className = "dd-meta";
    box.appendChild(line);
    var tr = trainBest(route);
    var note = el("div", "dd-meta");
    if (d.source === "nearby-ref") {
      var refHint = el("span", "dd-hint");
      refHint.textContent = "该日期源端无缓存价，显示" + (d.ref_offset ? "距此 " + d.ref_offset + " 天的最近有价日参考" : "最近有价日的参考价") + " · 点击下方按钮直达查当日实际价格";
      note.appendChild(refHint);
      note.appendChild(document.createTextNode(" "));
    }
    if (d.source === "interp") {
      var interpHint = el("span", "dd-hint");
      interpHint.textContent = "该日期源端无缓存价，价格为两侧真实价插值估算" +
        (d.flight_no ? " · 参考航班 " + d.flight_no + "（时刻以购票页为准）" : "") + " · 点击下方按钮直达查当日实际价格";
      note.appendChild(interpHint);
      note.appendChild(document.createTextNode(" "));
    }
    if (!hasTime) {
      var hint = el("span", "dd-hint");
      hint.textContent = "起降时刻以下单页为准 · 配置Amadeus密钥后国际线自动显示真实时刻";
      note.appendChild(hint);
      if (!isRT) note.appendChild(document.createTextNode(" "));
    }
    if (isRT) {
      note.appendChild(document.createTextNode("往返合计=去程+返程各自含税总价之和, 两段需分别下单"));
    }
    if (note.childNodes.length) box.appendChild(note);
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

  var TREND_IDS_MAIN = { svg: "trendSvg", cross: "trendCross", dot: "trendDot" };
  var TREND_IDS_RET = { svg: "trendRetSvg", cross: "trendRetCross", dot: "trendRetDot" };

  function renderTrendInto(boxId, deals, route, ids, combined) {
    var box = $(boxId);
    if (!route || !deals || !deals.length) { box.textContent = "暂无数据"; return; }
    var pts = deals.slice().sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    var th = route.threshold_total;
    var W = 760, H = 270, L = 52, R = 18, T = 26, B = 36;
    var lo = th, hi = th;
    pts.forEach(function (p) {
      if (p.total_price < lo) lo = p.total_price;
      if (p.total_price > hi) hi = p.total_price;
    });
    var pad = (hi - lo) * 0.16 || 60;
    lo -= pad * 0.6; hi += pad;
    function X(i) { return L + (W - L - R) * (pts.length === 1 ? 0.5 : i / (pts.length - 1)); }
    function Y(v) { return T + (H - T - B) * (1 - (v - lo) / (hi - lo)); }
    var P = pts.map(function (p, i) { return { x: X(i), y: Y(p.total_price) }; });
    function isEst(p) { return p.source === "nearby-ref" || p.source === "interp"; }
    var realIdxs = [];
    for (var r0 = 0; r0 < pts.length; r0++) if (!isEst(pts[r0])) realIdxs.push(r0);
    var pool = realIdxs.length ? realIdxs : pts.map(function (p, i) { return i; });
    var minIdx = pool[0];
    for (var m = 1; m < pool.length; m++)
      if (pts[pool[m]].total_price < pts[minIdx].total_price) minIdx = pool[m];

    function smooth(d) {
      // Monotone cubic (Fritsch-Carlson): Skyscanner-grade curve, no overshoot
      var n = d.length;
      if (!n) return "";
      if (n < 3) return "M " + d[0].x.toFixed(1) + " " + d[0].y.toFixed(1) +
        (n === 2 ? " L " + d[1].x.toFixed(1) + " " + d[1].y.toFixed(1) : "");
      var dx = [], ms = [];
      for (var q = 0; q < n - 1; q++) {
        dx.push(d[q + 1].x - d[q].x);
        ms.push((d[q + 1].y - d[q].y) / (dx[q] || 1));
      }
      var t = [ms[0]];
      for (var k = 1; k < n - 1; k++) t.push((ms[k - 1] * dx[k] + ms[k] * dx[k - 1]) / (dx[k - 1] + dx[k]));
      t.push(ms[n - 2]);
      for (var k2 = 0; k2 < n - 1; k2++) {
        if (ms[k2] === 0) { t[k2] = 0; t[k2 + 1] = 0; continue; }
        var a = t[k2] / ms[k2], b = t[k2 + 1] / ms[k2], s = a * a + b * b;
        if (s > 9) { var tau = 3 / Math.sqrt(s); t[k2] = tau * a * ms[k2]; t[k2 + 1] = tau * b * ms[k2]; }
      }
      var path = "M " + d[0].x.toFixed(1) + " " + d[0].y.toFixed(1);
      for (var i2 = 0; i2 < n - 1; i2++) {
        var h = (d[i2 + 1].x - d[i2].x) / 3;
        path += " C " + (d[i2].x + h).toFixed(1) + " " + (d[i2].y + t[i2] * h).toFixed(1) +
             ", " + (d[i2 + 1].x - h).toFixed(1) + " " + (d[i2 + 1].y - t[i2 + 1] * h).toFixed(1) +
             ", " + d[i2 + 1].x.toFixed(1) + " " + d[i2 + 1].y.toFixed(1);
      }
      return path;
    }
    var linePath = smooth(P);

    var s = [];
    s.push("<svg id=\"" + ids.svg + "\" viewBox=\"0 0 " + W + " " + H + "\" xmlns=\"http://www.w3.org/2000/svg\">");

    var stepX = pts.length > 1 ? (W - L - R) / (pts.length - 1) : 0;
    for (var w = 0; w < pts.length; w++) {
      var wd = weekday(pts[w].date);
      if (wd === "周六" || wd === "周日") {
        var wx = w === 0 ? L : X(w) - stepX / 2;
        var ww = w === 0 ? (pts.length > 1 ? stepX / 2 : W - L - R) : (w === pts.length - 1 ? W - R - wx : stepX);
        s.push("<rect x=\"" + wx.toFixed(1) + "\" y=\"" + T + "\" width=\"" + Math.max(0, ww).toFixed(1) + "\" height=\"" + (H - T - B) + "\" fill=\"rgba(23,32,64,0.03)\"/>");
      }
    }

    for (var g = 0; g <= 4; g++) {
      var v = lo + (hi - lo) * g / 4;
      var y = Y(v);
      s.push("<line x1=\"" + L + "\" y1=\"" + y.toFixed(1) + "\" x2=\"" + (W - R) + "\" y2=\"" + y.toFixed(1) + "\" stroke=\"rgba(23,32,64,0.08)\" stroke-width=\"1\"" + (g === 0 ? "" : " stroke-dasharray=\"2 5\"") + "/>");
      s.push("<text x=\"" + (L - 8) + "\" y=\"" + (y + 4).toFixed(1) + "\" fill=\"#66708a\" font-size=\"11\" text-anchor=\"end\">¥" + Math.round(v) + "</text>");
    }

    s.push("<rect x=\"" + L + "\" y=\"" + T + "\" width=\"" + (W - L - R) + "\" height=\"" + Math.max(0, Y(th) - T).toFixed(1) + "\" fill=\"rgba(220,38,38,0.04)\"/>");
    s.push("<line x1=\"" + L + "\" y1=\"" + Y(th) + "\" x2=\"" + (W - R) + "\" y2=\"" + Y(th) +
           "\" stroke=\"#dc2626\" stroke-width=\"1.5\" stroke-dasharray=\"6 4\"/>");
    s.push("<text x=\"" + (L + 8) + "\" y=\"" + (Y(th) - 8).toFixed(1) + "\" fill=\"#d93025\" font-size=\"10.5\" font-weight=\"600\">心理价位 ¥" + Math.round(th) + "</text>");

    var sum = 0;
    var avgPool = realIdxs.length ? realIdxs : pts.map(function (p, i) { return i; });
    for (var a = 0; a < avgPool.length; a++) sum += pts[avgPool[a]].total_price;
    var avg = sum / avgPool.length;
    s.push("<g><line x1=\"" + L + "\" y1=\"" + Y(avg).toFixed(1) + "\" x2=\"" + (W - R) + "\" y2=\"" + Y(avg).toFixed(1) +
           "\" stroke=\"#9aa0a6\" stroke-width=\"1\" stroke-dasharray=\"1.5 4.5\" stroke-linecap=\"round\"/>" +
           "<text x=\"" + (W - R - 4) + "\" y=\"" + (Y(avg) - 6).toFixed(1) + "\" fill=\"#5f6368\" font-size=\"10.5\" font-weight=\"600\" text-anchor=\"end\">均价 ¥" + Math.round(avg) + "</text></g>");
    s.push("<path d=\"" + linePath + "\" fill=\"none\" stroke=\"#4f46e5\" stroke-width=\"2.25\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>");

    var lstep = Math.max(1, Math.ceil(pts.length / 8));
    for (var j = 0; j < pts.length; j++) {
      if (j % lstep === 0 || j === pts.length - 1) {
        s.push("<text x=\"" + X(j).toFixed(1) + "\" y=\"" + (H - 12) + "\" fill=\"#66708a\" font-size=\"10\" text-anchor=\"middle\">" + fmtMD(pts[j].date) + "</text>");
      }
    }

    for (var k = 0; k < pts.length; k++) {
      if (k === minIdx) continue;
      var p = pts[k];
      var below = p.total_price < th;
      if (p.source === "interp") {
        s.push("<circle cx=\"" + X(k).toFixed(1) + "\" cy=\"" + Y(p.total_price).toFixed(1) +
               "\" r=\"3\" fill=\"#ffffff\" stroke=\"#d97706\" stroke-width=\"1.8\" stroke-dasharray=\"2.4 1.8\"><title>" +
               p.date + " " + weekday(p.date) + " ≈" + fmtMoney(p.total_price) + " 插值估算</title></circle>");
        continue;
      }
      if (below) s.push("<circle cx=\"" + X(k).toFixed(1) + "\" cy=\"" + Y(p.total_price).toFixed(1) + "\" r=\"5\" fill=\"rgba(24,128,56,0.12)\"/>");
      s.push("<circle cx=\"" + X(k).toFixed(1) + "\" cy=\"" + Y(p.total_price).toFixed(1) +
             "\" r=\"" + (below ? 3.2 : 2.2) + "\" fill=\"" + (below ? "#188038" : "#9aa0a6") + "\" stroke=\"#ffffff\" stroke-width=\"1.2\"><title>" +
             p.date + " " + weekday(p.date) + " " + fmtMoney(p.total_price) + " " +
             (p.source === "nearby-ref" ? "临近日参考" : "") + " " + (p.flight_no || "") + "</title></circle>");
    }

    var mp = pts[minIdx];
    var mx = X(minIdx), my = Y(mp.total_price);
    var mLabel = (combined ? "最低合计 ¥" : "最低 ¥") + Math.round(mp.total_price) + " · " + fmtMD(mp.date);
    var mLx = Math.min(Math.max(mx, L + 40), W - R - 40);
    s.push("<g>" +
           "<circle cx=\"" + mx.toFixed(1) + "\" cy=\"" + my.toFixed(1) + "\" r=\"4\" fill=\"#188038\" stroke=\"#ffffff\" stroke-width=\"1.5\"/>" +
           "<text x=\"" + mLx.toFixed(1) + "\" y=\"" + (my - 12).toFixed(1) + "\" fill=\"#188038\" font-size=\"11\" font-weight=\"700\" text-anchor=\"middle\">" + mLabel + "</text></g>");

    s.push("<line id=\"" + ids.cross + "\" x1=\"0\" y1=\"" + T + "\" x2=\"0\" y2=\"" + (H - B) + "\" stroke=\"rgba(23,32,64,0.35)\" stroke-width=\"1\" stroke-dasharray=\"3 3\" visibility=\"hidden\"/>");
    s.push("<circle id=\"" + ids.dot + "\" r=\"5\" fill=\"#0ea5e9\" stroke=\"#ffffff\" stroke-width=\"1.5\" visibility=\"hidden\"/>");
    s.push("</svg>");
    box.innerHTML = s.join("");

    var tip = document.createElement("div");
    tip.className = "trend-tip";
    box.appendChild(tip);
    var svg = box.querySelector("#" + ids.svg);
    svg.addEventListener("mousemove", function (e) {
      var rect = svg.getBoundingClientRect();
      var vx = (e.clientX - rect.left) * (W / rect.width);
      var best = 0, bd = Infinity;
      for (var n = 0; n < P.length; n++) { var dd = Math.abs(P[n].x - vx); if (dd < bd) { bd = dd; best = n; } }
      var q = pts[best];
      var cross = svg.querySelector("#" + ids.cross), dot = svg.querySelector("#" + ids.dot);
      cross.setAttribute("x1", P[best].x.toFixed(1)); cross.setAttribute("x2", P[best].x.toFixed(1));
      cross.removeAttribute("visibility");
      dot.setAttribute("cx", P[best].x.toFixed(1)); dot.setAttribute("cy", P[best].y.toFixed(1));
      dot.removeAttribute("visibility");
      var below2 = q.total_price < th;
      tip.innerHTML = "<b>" + fmtMD(q.date) + " " + weekday(q.date) + "</b>" +
        "<span class=\"" + (below2 ? "good" : "warn") + "\">¥" + Math.round(q.total_price) + "</span>" +
        "<i>" + (combined && q.ret_date
          ? "返程 " + fmtMD(q.ret_date) + " · 往返合计"
          : ((q.flight_no || "") + (q.dep_time ? " · " + q.dep_time : "") +
             (q.duration_text ? " · " + q.duration_text : "") +
             (q.source === "amadeus-fill" ? " · Amadeus补" : "") +
             (q.source === "interp" ? " · 插值估算" : "") +
             (q.source === "nearby-ref" ? " · 临近日参考" : "") +
             (q.source === "qunar-intl" ? " · 国际特价" : ""))) + "</i>";
      tip.style.display = "block";
      var bRect = box.getBoundingClientRect();
      tip.style.left = Math.min(Math.max(P[best].x / W * bRect.width - 70, 0), bRect.width - 156) + "px";
      tip.style.top = Math.max(P[best].y / H * bRect.height - 78, 0) + "px";
    });
    svg.addEventListener("mouseleave", function () {
      svg.querySelector("#" + ids.cross).setAttribute("visibility", "hidden");
      svg.querySelector("#" + ids.dot).setAttribute("visibility", "hidden");
      tip.style.display = "none";
    });
  }

  function renderTrend(route) {
    var isRT = !!(route && route.trip_type === "roundtrip" && route.combined_by_date);
    var deals = (route && route.deals) || [];
    if (isRT) {
      deals = deals.map(function (d) {
        var c = route.combined_by_date[d.date];
        if (!c) return d;
        var cp = {};
        for (var k in d) cp[k] = d[k];
        cp.total_price = c.total;
        cp.ret_date = c.ret_date;
        cp.ret_flight = c.ret_flight;
        return cp;
      });
    }
    renderTrendInto("trend", deals, route, TREND_IDS_MAIN, isRT);
  }

  function renderTop5(route) {
    var box = $("top5Box");
    box.textContent = "";
    var deals = (route && route.deals) || [];
    if (!deals.length) { box.textContent = "暂无数据"; return; }
    var th = route.threshold_total;
    var isRT = route && route.trip_type === "roundtrip" && route.combined_by_date;
    var rows = deals.map(function (d) {
      var cp = d;
      if (isRT) {
        var c = route.combined_by_date[d.date];
        if (c) {
          cp = {};
          for (var k in d) cp[k] = d[k];
          cp.total_price = c.total;
          cp.url = c.url || d.url;
        }
      }
      return cp;
    }).filter(function (d) {
      return d.source !== "nearby-ref" && d.source !== "interp";
    }).sort(function (a, b) { return a.total_price - b.total_price; }).slice(0, 5);
    var tbl = el("table", "top5-table");
    tbl.innerHTML = "<thead><tr><th>#</th><th>日期</th><th>总价</th><th>航班</th><th>托运</th><th></th></tr></thead>";
    var tb = el("tbody");
    rows.forEach(function (d, i) {
      var tr = el("tr", d.total_price < th ? "cheap-row" : "");
      var bagTxt = d.baggage === false ? "无免费托运" : (d.baggage === true ? "含免费托运" : "以舱位为准");
      tr.innerHTML =
        "<td>" + (i + 1) + "</td>" +
        "<td><b>" + fmtMD(d.date) + "</b> " + weekday(d.date) + "</td>" +
        "<td class=\"price-td\" data-below=\"" + (d.total_price < th ? "1" : "0") + "\"><b>¥" + Math.round(d.total_price) + "</b></td>" +
        "<td>" + (d.airline || "—") + " " + (d.flight_no || "") +
          (d.dep_time ? "<br><span class=muted>" + d.dep_time + "起飞</span>" : "") +
          (d.source === "amadeus-fill" ? " <span class='badge amber'>Amadeus补</span>" : "") + "</td>" +
        "<td>" + bagTxt + "</td>" +
        "<td><a class=\"btn small\" href=\"" + (d.url || "#") + "\" target=\"_blank\">直达购票 →</a></td>";
      tb.appendChild(tr);
    });
    tbl.appendChild(tb);
    box.appendChild(tbl);
  }

  function renderDestIntel(route) {
    var box = $("destIntel");
    if (!route) { box.classList.add("hidden"); return; }
    box.classList.remove("hidden");
    box.textContent = "";
    var head = el("div", "card-head");
    head.appendChild(el("h3", "", "📍 目的地情报 · " + route.to_city));
    head.appendChild(el("span", "muted", "天气/汇率 · 开放API实时获取 · 免Key"));
    box.appendChild(head);
    var body = el("div", "intel-body");
    body.textContent = "加载中…";
    box.appendChild(body);
    fetch("/api/dest-intel?route=" + encodeURIComponent(route.id))
      .then(function (r) { return r.json(); })
      .then(function (j) {
        body.textContent = "";
        if (!j || !j.ok) { body.textContent = "情报服务暂不可达"; return; }
        if (j.weather && j.weather.length) {
          var wt = el("div", "wx-strip");
          j.weather.forEach(function (w) {
            var d = el("div", "wx-day");
            d.innerHTML = "<span class=wx-ico>" + w.icon + "</span>" +
              "<span class=wx-t><b>" + w.hi + "°</b>/" + w.lo + "°</span>" +
              "<span class=wx-date>" + fmtMD(w.date) + " " + weekday(w.date) + "</span>" +
              "<span class=wx-label>" + w.label + (w.pop && w.pop >= 30 ? " ·雨" + w.pop + "%" : "") + "</span>";
            wt.appendChild(d);
          });
          var wTitle = el("div", "intel-title", "未来7天天气");
          body.appendChild(wTitle);
          body.appendChild(wt);
        }
        if (j.fx) {
          var fx = el("div", "fx-line");
          fx.innerHTML = "💱 参考汇率: <b>¥1000 ≈ " + j.fx.per_1000 + " " + j.fx.currency + "</b>" +
            "<span class=muted> · open.er-api.com 每日更新</span>";
          body.appendChild(fx);
        }
        if (!j.weather && !j.fx) body.textContent = "暂无情报数据";
      })
      .catch(function () { body.textContent = "情报服务暂不可达"; });
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
    renderHero(route);
    renderKpis(route);
    renderVerdict(route);
    renderCalendarView(route);
    renderDayDetail(route);
    renderTrend(route);
    var isRT = !!(route && route.trip_type === "roundtrip");
    $("returnTrendCard").classList.toggle("hidden", !isRT);
    $("trendTitle").textContent = isRT ? "往返合计趋势 (按去程日期)" : "价格趋势";
    $("trendHint").textContent = isRT
      ? "每个点=该去程日期的最优往返组合价 · 绿点=合计低于心理价位 · 悬停看明细"
      : "绿点=低于心理价位 · 悬停看每日明细";
    if (isRT) renderTrendInto("trendReturn", (route && route.return_deals) || [], route, TREND_IDS_RET, false);
    renderTop5(route);
    renderDestIntel(route);
    renderTrains(route);
    checkMobileAlerts(route);
  }

  function renderRouteTabs() {
    var box = $("routeTabs");
    box.textContent = "";
    if (!S.snap || !S.snap.routes) return;
    S.snap.routes.forEach(function (r) {
      var b = el("button", r.id === (S.routeId || (S.snap.routes[0] && S.snap.routes[0].id)) ? "active" : "",
        r.from_city + (r.trip_type === "roundtrip" ? " ⇄ " : " → ") + r.to_city);
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
          trip_type: "oneway",
          intl: false,
          from_iata: "",
          to_iata: "",
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
    var title = el("div", "rc-title",
      r.from_city + (r.trip_type === "roundtrip" ? " ⇄ " : " → ") + r.to_city);
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

    function refreshTitle() {
      title.textContent = r.from_city + (r.trip_type === "roundtrip" ? " ⇄ " : " → ") + r.to_city;
    }

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

    var optLine = el("div", "city-line");
    var ttF = el("label", "field");
    ttF.appendChild(el("span", "f-label", "行程类型"));
    var ttSel = el("select");
    [["oneway", "单程"], ["roundtrip", "往返(去+返合计比价)"]].forEach(function (o) {
      var op = el("option", null, o[1]);
      op.value = o[0];
      ttSel.appendChild(op);
    });
    ttSel.value = r.trip_type === "roundtrip" ? "roundtrip" : "oneway";
    ttSel.addEventListener("change", function () {
      r.trip_type = ttSel.value;
      refreshTitle();
      refreshThLabel();
    });
    ttF.appendChild(ttSel);
    optLine.appendChild(ttF);

    var intlF = el("label", "field check");
    var icb = el("input");
    icb.type = "checkbox";
    icb.checked = !!r.intl;
    icb.addEventListener("change", function () { r.intl = icb.checked; });
    intlF.appendChild(icb);
    intlF.appendChild(el("span", "f-label", "国际航线(Amadeus)"));
    optLine.appendChild(intlF);

    function iataField(labelText, key, ph) {
      var lf = el("label", "field");
      lf.appendChild(el("span", "f-label", labelText));
      var inp = el("input");
      inp.type = "text";
      inp.value = r[key] || "";
      inp.maxLength = 3;
      inp.placeholder = ph;
      inp.style.textTransform = "uppercase";
      inp.addEventListener("input", function () {
        r[key] = inp.value.trim().toUpperCase();
      });
      lf.appendChild(inp);
      return lf;
    }
    optLine.appendChild(iataField("出发IATA", "from_iata", "如 HGH"));
    optLine.appendChild(iataField("到达IATA", "to_iata", "如 NRT"));
    optLine.appendChild(el("span", "muted", "国际线走Amadeus含税价; 往返=去程+返程合计对比阈值"));
    card.appendChild(optLine);

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

    var lb2 = el("label", null, "");
    function refreshThLabel() {
      lb2.textContent = r.trip_type === "roundtrip"
        ? "心理价位·往返合计含税(元)"
        : "心理价位·含税总价(元)";
    }
    refreshThLabel();
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
    var ama = (S.cfg.sources && S.cfg.sources.amadeus) || {};
    $("amaEnv").value = ama.env === "prod" ? "prod" : "test";
    $("amaId").value = ama.client_id || "";
    $("amaSecret").value = ama.client_secret || "";
    $("schInterval").value = S.cfg.schedule.interval_minutes;
    $("schJitter").value = S.cfg.schedule.jitter_minutes;
    $("webHost").value = S.cfg.webui.host;
    $("webPort").value = S.cfg.webui.port;

    $("taxAirport").oninput = function () { S.cfg.tax.airport_fee = parseFloat(this.value) || 0; };
    $("taxFuel").oninput = function () { S.cfg.tax.fuel_surcharge = parseFloat(this.value) || 0; };
    $("taxIncluded").onchange = function () { S.cfg.tax.calendar_price_includes_tax = this.checked; };
    $("amaEnv").onchange = function () {
      S.cfg.sources = S.cfg.sources || {};
      S.cfg.sources.amadeus = S.cfg.sources.amadeus || {};
      S.cfg.sources.amadeus.env = this.value;
    };
    $("amaId").oninput = function () {
      S.cfg.sources = S.cfg.sources || {};
      S.cfg.sources.amadeus = S.cfg.sources.amadeus || {};
      S.cfg.sources.amadeus.client_id = this.value.trim();
    };
    $("amaSecret").oninput = function () {
      S.cfg.sources = S.cfg.sources || {};
      S.cfg.sources.amadeus = S.cfg.sources.amadeus || {};
      S.cfg.sources.amadeus.client_secret = this.value;
    };
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
      r.trip_type = r.trip_type === "roundtrip" ? "roundtrip" : "oneway";
      r.intl = !!r.intl;
      r.from_iata = (r.from_iata || "").trim().toUpperCase();
      r.to_iata = (r.to_iata || "").trim().toUpperCase();
      if (r.intl && !(r.from_iata && r.to_iata)) {
        throw new Error("线路 " + (i + 1) + " 启用国际航线需填写出发/到达IATA三字码");
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
    "qunar-intl": "去哪儿·国际特价",
    "12306-train": "12306·车票查询",
    "amadeus-intl": "Amadeus·国际低价",
    "amadeus-fill": "Amadeus·缺价补全",
    "amadeus-times": "Amadeus·时刻增强",
    "nearby-ref": "临近日参考价",
    "interp": "插值估算价",
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

  var SRC_LABELS = {
    "qunar-calendar": "去哪儿日历", "12306-train": "12306车次",
    "qunar-intl": "去哪儿国际", "amadeus-intl": "Amadeus国际",
    "amadeus-fill": "Amadeus补价", "push": "推送"
  };

  function renderSourceHealth(health) {
    var wrap = el("div", "src-health");
    wrap.appendChild(el("div", "src-health-title", "数据源健康"));
    (health.sources || []).forEach(function (s) {
      var cls = s.degraded ? "bad" : ((s.score !== null && s.score !== undefined && s.score < 85) || s.consecutive_fails ? "warn" : "ok");
      var chip = el("div", "src-chip " + cls);
      chip.appendChild(el("span", "src-dot"));
      chip.appendChild(el("span", "src-name", SRC_LABELS[s.source] || s.source));
      chip.appendChild(el("span", "src-meta",
        (s.score === null || s.score === undefined ? "--分" : s.score + "分") +
        (s.degraded ? " · 已降级" : (s.consecutive_fails ? " · 波动" : " · 正常"))));
      if (s.degraded || s.consecutive_fails) {
        var det = el("div", "src-diag");
        var cands = (s.diagnose && s.diagnose.candidates) || [];
        if (cands.length) {
          cands.forEach(function (c) {
            det.appendChild(el("div", "src-diag-row", "ⓘ " + c.cause + " → " + c.action));
          });
        } else {
          det.appendChild(el("div", "src-diag-row", "最近错误: " + (s.last_error || "-")));
        }
        chip.appendChild(det);
      }
      wrap.appendChild(chip);
    });
    return wrap;
  }

  function renderCrawl(doc) {
    var box = $("crawlPanel");
    box.textContent = "";
    if (doc && doc.health && (doc.health.sources || []).length) {
      box.appendChild(renderSourceHealth(doc.health));
    }
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

  function gotoTab(name) {
    var btn = document.querySelector('#mainTabs button[data-tab="' + name + '"]');
    if (btn) btn.click();
  }

  /* ---------- 事件绑定 ---------- */

  function refreshTab(name) {
    if (name === "dash") renderDash();
    if (name === "crawl") loadCrawl();
    if (name === "routes") renderRoutesEditor();
    if (name === "sources") renderSources();
    if (name === "push") { renderPush(); loadAlerts(); }
    if (name === "logs") loadLog();
  }

  function bindTabs() {
    var btns = document.querySelectorAll("#mainTabs button");
    btns.forEach(function (b) {
      b.addEventListener("click", function () {
        btns.forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active");
        document.querySelectorAll(".tab-panel").forEach(function (p) { p.classList.remove("active"); });
        $("tab-" + b.dataset.tab).classList.add("active");
        refreshTab(b.dataset.tab);
      });
    });
    var initTab = (location.hash || "").replace("#", "");
    if (initTab) gotoTab(initTab);
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
        trip_type: "oneway",
        intl: false,
        from_iata: "",
        to_iata: "",
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
    $("btnAmaTest").addEventListener("click", function () {
      var btn = $("btnAmaTest");
      var out = $("amaTestResult");
      btn.disabled = true;
      out.className = "muted";
      out.textContent = "验证中…";
      post("/api/config", cleanCfgForSave()).then(function () {
        return post("/api/amadeus-test");
      }).then(function (resp) {
        out.className = "ok-note";
        out.textContent = "✓ " + (resp.message || "密钥有效");
        toast("Amadeus 连接成功");
      }).catch(function (e) {
        out.className = "err-note";
        out.textContent = "✗ " + e.message;
        toast("Amadeus 验证失败: " + e.message);
      }).finally(function () { btn.disabled = false; });
    });
    $("btnRefreshLog").addEventListener("click", loadLog);
    $("btnRefreshCrawl").addEventListener("click", loadCrawl);
    $("btnViewCal").addEventListener("click", function () {
      S.calView = "cal";
      renderCalendarView(curRoute());
    });
    $("btnViewBars").addEventListener("click", function () {
      S.calView = "bars";
      renderCalendarView(curRoute());
    });
    $("btnNotify").addEventListener("click", function () {
      if (typeof Notification === "undefined") {
        toast("此浏览器不支持系统通知");
        return;
      }
      Notification.requestPermission().then(function (p) {
        toast(p === "granted" ? "系统通知已开启，低于心理价位会弹提醒" :
              p === "denied" ? "通知被浏览器拒绝，请在设置中允许" : "通知未开启");
      });
    });
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
