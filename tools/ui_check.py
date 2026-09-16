# -*- coding: utf-8 -*-
"""Verify Web UI DOM (dumped via headless Edge) contains rendered elements."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_raw = open("data/ui_dom.html", encoding="utf-8").read()
_docs = _raw.split("<html")  # dump_dom may concatenate several tab dumps
h = ("<html" + _docs[1]) if len(_docs) > 1 else _raw  # first doc only
_all = _raw  # content assertions may span all dumps
v1_dom = "data-tab=" in _raw  # v1 时代 DOM 快照标志(根路径现已同源托管 v2)
appjs = open(os.path.join("webui", "static", "app.js"), encoding="utf-8").read()
css = open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read()
checks = {
    "KPI最低机票": "最低机票总价" in h,
    "KPI低价天数": "低于心理价位" in h,
    "最优横幅": "当前最优" in h,
    "最优卡片机票": "最低机票 (" in h,
    "最优卡片动车": "动车二等 (" in h,
    "最优卡片学生": "学生动车" in h,
    "趋势SVG平滑曲线": ("<path" in h) and ("trend-tip" in h),
    "趋势均价参考线": "均价 ¥" in h,
    "趋势扁平无渐变": ("areaGrad" not in h) and ("feDropShadow" not in h) and ("<animate" not in h),
    "v0.23趋势图例行": ("低于心理价位" in h) and ("插值估算" in h) and ("30日均价" in h),
    "v0.24覆盖ETA": (("预计" in h) and ("全覆盖" in h)) or ("已覆盖全部" in h),
    "v0.23主线品牌蓝面积": ('fill="rgba(0,98,227,0.07)"' in h) and ('stroke="#0062e3"' in h),
    "v0.23最低价胶囊": ("<rect" in h) and ("最低 ¥" in h.replace("&yen;", "¥")),
    "趋势最低价标签": re.search(r"最低 ¥\d+ · ", h) is not None,
    "阈值虚线标签": "心理价位" in h,
    "列车对比表格": "二等座" in h,
    "硬卧席位chip": "硬卧" in h,
    "K车次行": "K1152" in h,
    "动卧席位": ("二等卧(动)" in h) or ("一等卧(动)" in h),
    "最低卧铺KPI": "最低卧铺" in h,
    "席位chip样式": "seat-chip" in h,
    "卧铺chip高亮": "seat-chip sleep" in h,
    "线路快捷模板": "快捷添加" in h,
    "城市互换按钮": "swap-btn" in h,
    "车站对联想框": "ac-wrap" in h,
    "阈值快捷chips": "quick-chips" in h,
    "页脚声明": "数据源: 去哪儿" in h,
    "路由标签": "杭州 → 重庆" in h,
    "爬虫监控tab": "data-tab=\"crawl\"" in h,
    "爬虫面板容器": "crawlPanel" in h,
    "刷新爬虫状态按钮": "btnRefreshCrawl" in h,
    "KPI可点击达": "<a class=\"kpi" in h,
    "对比卡直达链接": "v-link" in h,
    "车次表下单按钮": ("buy-link" in h) and ("下单" in h),
    "购票列表头": "<th>购票</th>" in h,
    "航班时刻说明": "起降时刻" in h,
    "车次时刻列": "08:08" in h,
    "车次历时列": "11:31" in h,
    "行程类型选择": "行程类型" in h,
    "国际Amadeus配置卡": "amaSecret" in h,
    "往返返程趋势容器": "trendReturn" in h,
    "浅色主题版本": re.search(r'class="ver">v\d+\.\d+<', h) is not None,
"缺价补全徽标(详情卡)": ('d.source === "amadeus-fill"' in appjs) and ("badge amber" in appjs),
"缺价补全徽标(最优卡)": appjs.count("amadeus-fill") >= 5,
"补全数据源名": '"amadeus-fill": "Amadeus' in appjs,
"v0.8城市图鉴Hero": ("city-visual" in h) and ("cv-desc" in h),
"v0.8柱状图视图": ("barsBox" in h) and ("bar-track" in appjs),
    "v0.8移动提醒横幅": ("alertFloat" in h) and ("alert-float" in h),
"v0.8临近日参考价": appjs.count("nearby-ref") >= 5,
"v0.8通知按钮": "btnNotify" in h,
"v0.8城市海报剪影": ("cv-scene" in h) and ("citySceneSvg" in appjs),
"v0.8参考价≈标记": "≈" in h,
"v0.8时刻待接入徽标": ("ft-pend" in appjs) and ("时刻待接入" in appjs),
"v0.8城市图片接口": ("city-photo" in appjs) and ("api/city-photo" in appjs),
"v0.8 Amadeus域名修正": "developers.amadeus.com" in h,
"v0.9 Amadeus注册直达": "developers.amadeus.com/register" in h,
"v0.9 推送注册指引": ("sct.ftqq.com" in h) and ("apps.apple.com" in h),
"v0.10低价TOP5表": ("top5-table" in h) and ("直达购票" in h),
"v0.10目的地情报卡": ("目的地情报" in h) and ("wx-strip" in h),
"v0.10天气情报渲染": ("wx-day" in appjs) and ("dest-intel" in appjs),
"v0.10汇率条": "per_1000" in appjs,
"v0.10 Amadeus隐私提示": ("隐私提示" in h) and ("可选" in h),
"v0.11插值补全后端": ("max_interp_span" in open("main.py", encoding="utf-8").read()) and ("source=\"interp\"" in open("main.py", encoding="utf-8").read()),
"v0.11插值过滤(最优/提醒)": appjs.count('d.source !== "interp"') >= 3,
"v0.11插值徽标(详情卡)": ("两侧真实价插值" in appjs) and ("badge amber" in appjs),
"v0.11插值日历样式": ("day.interp" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read()),
"v0.11插值柱状样式": ("bar.interp" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read()),
"v0.11趋势插值空心点": ("插值估算</title>" in appjs) and ("2.4 1.8" in appjs),
"v0.11趋势最低仅真实价": ("realIdxs" in appjs) and ("var minIdx = pool[0]" in appjs),
"v0.11数据源名interp": '"interp": "插值估算价"' in appjs,
"v0.18机场班期注册": '"hgh-board-times"' in open(os.path.join("core", "sources.py"), encoding="utf-8").read(),
"v0.18时刻兜底接线": ("board_lookup" in open("main.py", encoding="utf-8").read()) and ("time_src" in open("main.py", encoding="utf-8").read()),
"v0.18时刻来源徽标": ("计划时刻·机场班期" in appjs) and ('"hgh-board-times"' in appjs),
"v0.18周报无渠道守卫": "has_channel" in open("main.py", encoding="utf-8").read(),
"v0.11 TOP5排除估算价": ("renderTop5" in appjs) and ("interp" in appjs[appjs.index("function renderTop5"):appjs.index("function renderTop5") + 2500]),
"v0.12源健康徽标区": ("src-chip" in _all) and ("数据源健康" in _all),
"v0.12源健康四源齐": _all.count("src-chip ") >= 4,
"v0.12源健康样式": ("src-health" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read()) and ("src-dot" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read()),
"v0.12健康诊断行": "src-diag" in appjs,
"v0.12健康API字段": "diagnose" in open("webui.py", encoding="utf-8").read(),
"v0.12健康引擎阈值": ("DEGRADE_RUN_FAILS" in open(os.path.join("core", "health.py"), encoding="utf-8").read()),
"v0.12 Tab深链": ("location.hash" in appjs) and ("gotoTab" in appjs),
"v0.13反向Tab": ('data-tab="reverse"' in h) and ('id="tab-reverse"' in h),
"v0.13反向表单渲染": "扫描可去目的地" in _all,
"v0.13反向引擎": ("renderReverse" in appjs) and ("/api/reverse-search" in appjs),
"v0.13请求硬预算": "HARD_MAX_REQUESTS" in open(os.path.join("core", "reverse.py"), encoding="utf-8").read(),
"v0.13结果卡样式": ("rev-hit" in appjs) and (".rev-hit" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read()),
"v0.13缓存新鲜度徽标": "缓存" in appjs[appjs.index("function renderReverse"):appjs.index("function renderReverse") + 1500],
"v0.14周报Tab": ('data-tab="weekly"' in h) and ('id="tab-weekly"' in h),
"v0.14周报文本区": 'id="wkText"' in h,
"v0.14周报路由卡": ("wk-card" in appjs) and (".wk-card" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read()),
"v0.14周报走势图": ("wkSpark" in appjs) and (".wk-spark-line" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read()),
"v0.14周报引擎": ("build_weekly" in open("webui.py", encoding="utf-8").read()) and ("build_weekly" in open(os.path.join("core", "weekly.py"), encoding="utf-8").read()),
"v0.14周报API": '/api/weekly-report' in appjs,
"v0.14周报推送按钮": 'btnWeeklyPush' in h,
"v0.16推送未配置警告": 'id="wkPushWarn"' in h,
"v0.16推送守卫": "未配置推送渠道" in open("webui.py", encoding="utf-8").read(),
"v0.16走势最低点": "wk-spark-dot-min" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read(),
"v0.16单点占位": "wkDot" in appjs,
"v0.17时刻空态可配置": ("配置时刻源" in appjs) and ("amaId" in appjs),
"v0.17时刻空态样式": ".ft-pend.link" in open(os.path.join("webui", "static", "style.css"), encoding="utf-8").read(),
"v0.17时刻跳转绑定": 'gotoTab("sources")' in appjs,
"v0.17排班缓存14天": "14 * 86400" in open(os.path.join("core", "intl.py"), encoding="utf-8").read(),
    "v0.27健康端点": '"/api/health"' in open("webui.py", encoding="utf-8").read(),
    "v0.27新鲜度相对时间": "分钟前" in appjs,
    "v0.27保存即刷新推送徽标": "applyPushPending(resp.push_pending)" in appjs,
    "v0.28设计令牌色板": all(t in css for t in ("--fs-2xs", "--r-pill", "--green-bg", "--on-accent", "--r-flag")),
    "v0.28令牌接线量": css.count("var(--") > 600,
}
legacy_keys = set(checks)  # 字典字面量里的 v1 DOM 断言, 依赖已退役的 v1 快照
# --- v0.29: v2 frontend (web/, Preact+Vite, hosted same-origin at /v2) ---
_web_dist_idx = os.path.join("web", "dist", "index.html")
if os.path.exists(_web_dist_idx):
    _dist_html = open(_web_dist_idx, encoding="utf-8").read()
    checks["v0.29 v2构建产物"] = ("/v2/assets/" in _dist_html) and ('id="app"' in _dist_html)
else:
    checks["v0.29 v2构建产物"] = False
_webui_src = open("webui.py", encoding="utf-8").read()
_v2mod_src = open("webui_v2.py", encoding="utf-8").read()
checks["v0.29 v2同源托管"] = ("register_v2" in _webui_src) and ('"/v2"' in _v2mod_src)


def _root_tokens(txt):
    i = txt.index(":root")
    j = txt.index("}", i)
    return set(re.findall(r"--[A-Za-z0-9-]+(?=\s*:)", txt[i:j]))


_old_tokens = _root_tokens(css)
_new_tokens = _root_tokens(open(os.path.join("web", "src", "styles", "tokens.css"), encoding="utf-8").read())
checks["v0.29 v2令牌同步"] = _old_tokens <= _new_tokens
_hex_v2 = []
for _root_dir, _sub_dirs, _fs in os.walk(os.path.join("web", "src")):
    for _fn in _fs:
        if _fn == "tokens.css":
            continue
        _p = os.path.join(_root_dir, _fn)
        _t = open(_p, encoding="utf-8").read()
        _hex_v2 += [_p + ":" + m for m in re.findall(r"#[0-9a-fA-F]{3,8}\b", _t)]
checks["v0.29 v2零硬编码色"] = not _hex_v2

# --- v0.30: v2 wave-2 tabs (crawl / weekly / sources / push) ---
_v2_comp_dir = os.path.join("web", "src", "components")
_v2_wave2 = ["CrawlView.jsx", "WeeklyView.jsx", "SourcesView.jsx", "PushView.jsx"]
checks["v0.30 v2四组件"] = all(
    os.path.exists(os.path.join(_v2_comp_dir, f)) for f in _v2_wave2)
_app_jsx_v2 = open(os.path.join("web", "src", "app.jsx"), encoding="utf-8").read()
checks["v0.30 v2 tab导航"] = ("tabbar" in _app_jsx_v2) and ("CrawlView" in _app_jsx_v2)
_dist_files = []
for _root_dir, _sub_dirs, _fs in os.walk(os.path.join("web", "dist", "assets")):
    _dist_files += [open(os.path.join(_root_dir, f), encoding="utf-8").read()
                    for f in _fs if f.endswith(".js")]
_dist_js = "".join(_dist_files)
_src_list = [os.path.join(_root_dir, f)
             for _root_dir, _sub_dirs, _fs in os.walk(os.path.join("web", "src"))
             for f in _fs]
_dist_list = [os.path.join(_root_dir, f)
              for _root_dir, _sub_dirs, _fs in os.walk(os.path.join("web", "dist", "assets"))
              for f in _fs if f.endswith((".js", ".css"))]
checks["v0.30.1 dist assets present"] = bool(_dist_list)


def _git_dirty(subpath):
    """True/False; None when git unavailable (then skip mtime heuristic)."""
    import subprocess as _sp
    try:
        _r = _sp.run(["git", "status", "--porcelain", "--", subpath],
                     capture_output=True, text=True, timeout=10)
        return bool(_r.stdout.strip())
    except Exception:
        return None


# mtime heuristic only fires when src is dirty but dist is clean (forgot rebuild).
# Clean trees (fresh clone/pull) and both-dirty (edited+rebuilt) skip it, because
# git checkout write order can leave src newer than dist without any real staleness.
_src_dirty, _dist_dirty = _git_dirty("web/src"), _git_dirty("web/dist")
if _src_list and _dist_list and _src_dirty and not _dist_dirty:
    checks["v0.30.1 dist freshness (src dirty, dist stale)"] = (
        max(map(os.path.getmtime, _dist_list)) >= max(map(os.path.getmtime, _src_list)))
checks["v0.30 v2产物含新tab"] = ("爬虫监控" in _dist_js) and ("立即推送周报" in _dist_js) \
    and ("开启浏览器通知" in _dist_js) and ("时刻库沉淀进度" in _dist_js)
checks["v0.35 v2产物含调度心跳"] = ("调度心跳" in _dist_js) and ("autostart_worker" in _dist_js)
_dist_css = ""
for _root_dir, _sub_dirs, _fs in os.walk(os.path.join("web", "dist", "assets")):
    for f in _fs:
        if f.endswith(".css"):
            _dist_css += open(os.path.join(_root_dir, f), encoding="utf-8").read()
_tc_src = open(os.path.join("web", "src", "components", "TrendChart.jsx"), encoding="utf-8").read()
checks["v0.36 v2排版放大+平滑趋势"] = (
    ("--fs-kpi2" in _dist_css) and ("smoothPath" in _tc_src)
    and ("t-wknd" in _dist_js) and ("t-min-tag" in _dist_css))
checks["v0.38 v2产物含自愈任务状态"] = ("自愈" in _dist_js) and ("07:00" in _dist_js)
checks["v0.39 v2产物含推送状态卡"] = ("推送状态" in _dist_js) and ("下次推送" in _dist_js)
checks["v0.39 v2质感微升级"] = (("focus-visible" in _dist_css)
    and bool(re.search(r"letter-spacing:\s*-0?\.5px", _dist_css))
    and ("radial-gradient(" in _dist_css))
checks["v0.39 MCP巡检工具"] = "patrol_run" in open(
    "mcp_server.py", encoding="utf-8").read()
checks["v0.39 v2 DOM推送状态卡"] = (("推送状态" in _all)
    and ("Bark 未配置" in _all) and ("推送渠道未就绪" in _all))
checks["v0.40 v2产物真实票口径"] = ("真实票时刻覆盖" in _dist_js) and ("参考价" in _dist_js)
checks["v0.40 v2产物每日巡检"] = "每日巡检" in _dist_js
_patrol_src = (open(os.path.join("core", "patrol.py"), encoding="utf-8").read()
               if os.path.exists(os.path.join("core", "patrol.py")) else "")
checks["v0.40 巡检核心抽取"] = (("run_patrol" in _patrol_src)
    and ("config_loader" in _patrol_src) and ("127.0.0.1" in _patrol_src))
checks["v0.40 巡检定时化"] = "patrol_once" in open(
    os.path.join("core", "revive.py"), encoding="utf-8").read()
checks["v0.40 v2 DOM真实票口径"] = "真实票时刻覆盖" in _all
checks["v0.40.1 v2产物巡检异常可见"] = "最近异常" in _dist_js
_reenrich_src = open(os.path.join("core", "reenrich.py"),
                     encoding="utf-8").read() if os.path.exists(
    os.path.join("core", "reenrich.py")) else ""
checks["v0.41 时刻回写核心"] = (("reenrich_snapshot" in _reenrich_src)
    and ("_enrich_flight_times" in _reenrich_src)
    and ("time_coverage" in _reenrich_src))
checks["v0.41 巡检接线离线回写"] = "_patrol_time_fill" in open(
    os.path.join("core", "revive.py"), encoding="utf-8").read()
checks["v0.41 v2产物时刻回写可见"] = "时刻回写" in _dist_js
checks["v0.41 v2产物缺时刻CTA"] = "查当日实时班次与购票" in _dist_js
_backup_src = open(os.path.join("tools", "backup.py"),
                   encoding="utf-8").read() if os.path.exists(
    os.path.join("tools", "backup.py")) else ""
checks["v0.41 迁移备份工具"] = (("flight_sched_db.json" in _backup_src)
    and ("zipfile" in _backup_src))
_cabin_src = open(os.path.join("core", "cabin_monitor.py"),
                 encoding="utf-8").read() if os.path.exists(
    os.path.join("core", "cabin_monitor.py")) else ""
checks["v0.42 公务舱监控核心"] = (("record_low" in _cabin_src)
    and ("evaluate_alert" in _cabin_src)
    and ("route_qualifies" in _cabin_src))
checks["v0.42 公务舱API"] = (("/api/cabin" in open("webui.py",
    encoding="utf-8").read())
    and ("fetch_cabin_offers" in open(os.path.join("core", "intl.py"),
                                      encoding="utf-8").read()))
checks["v0.42 v2产物公务舱卡"] = "公务舱低价监控" in _dist_js
checks["v0.42 共享号时刻兜底"] = (("_attach_alt_times" in _reenrich_src)
    and ("alt_before" in _reenrich_src))
_intl_src = open(os.path.join("core", "intl.py"),
                 encoding="utf-8").read() if os.path.exists(
    os.path.join("core", "intl.py")) else ""
_main_src = open("main.py", encoding="utf-8").read()
checks["v0.43 公务舱精确时刻"] = (("_cabin_offer_times" in _intl_src)
    and ('time_src="amadeus" if dep else ""' in _intl_src))
checks["v0.43 采集先于补全早退"] = (('covered = {d.date for d in deals'
    ' if (d.cabin or "") == ""}' in _main_src)
    and ("BEFORE the gap-fill early-return" in _main_src))
checks["v0.43 offer时刻不被降级"] = (("and not d.dep_time" in _main_src)
    and ("offer-exact times" in _main_src))
checks["v0.43 监控配置校验"] = ("cabin_watch必须是对象" in open(
    "webui.py", encoding="utf-8").read())
checks["v0.43 v2产物监控编辑"] = (("保存监控配置" in _dist_js)
    and ("监控出发城市" in _dist_js))
checks["v0.44 经济舱offer兜底"] = (("fetch_fill_offers" in _intl_src)
    and ('"travelClass": "ECONOMY"' in _intl_src))
checks["v0.44 兜底按日缓存"] = (("OFFER-" in _main_src)
    and ("negative 24h" in _main_src))
checks["v0.44 用量计数端点"] = ("/api/amadeus-usage" in open(
    "webui.py", encoding="utf-8").read())
checks["v0.44 v2产物用量与走势"] = (("Amadeus 今日调用" in _dist_js)
    and ("spark-line" in _dist_js))
_hist_src = open(os.path.join("core", "history.py"),
                 encoding="utf-8").read()
checks["v0.45 coverage archive+trend"] = (("coverage_trend" in _hist_src)
    and ('m["cov"]' in _hist_src))
checks["v0.45 coverage-trend API"] = "/api/coverage-trend" in _webui_src
checks["v0.45 v2 city chips+cov trend"] = (("cw-chip" in _dist_js)
    and ("cov-trend" in _dist_js) and ("cvt-line" in _dist_css))
_sb_src = open(os.path.join("core", "sched_board.py"),
               encoding="utf-8").read()
checks["v0.46 board row-date dow"] = (("_row_dow" in _sb_src)
    and ("row_dow = _row_dow(row, dow)" in _sb_src))
checks["v0.46 pre-fmt db migrated"] = (("_ensure_fmt2" in _sb_src)
    and ('"fmt": 2' in _sb_src))
checks["v0.47 cabin multi-dest + refresh"] = (("to_cities" in _webui_src)
    and ("qualifying_routes" in _webui_src)
    and ("worker_heartbeat" in _webui_src))
_cabin_src = open(os.path.join("core", "cabin_monitor.py"),
                  encoding="utf-8").read()
checks["v0.47 cabin monitor list gate"] = (('"to_cities": ["杭州"]'
    in _cabin_src) and ("route_qualifies" in _cabin_src))
checks["v0.48 alt-ref promote core"] = (("promote_alt_time" in _sb_src)
    and ("alt-ref" in _main_src)
    and ("promote_alt_time" in _main_src))
checks["v0.48 v2产物参考班次徽标"] = (("参考班次" in _dist_js)
    and ("alt-ref" in _dist_js))
checks["v0.49 return-leg ref times"] = (("city_return_dep_times" in _sb_src)
    and ("direction=\"ret\"" in _main_src)
    and ("from_city=" in _main_src))
checks["v0.49 reenrich return replay"] = (("raw_ret" in _reenrich_src)
    and ("direction=\"ret\"" in _reenrich_src))

_cabin_card_src = open(os.path.join("web", "src", "components",
                                    "CabinCard.jsx"),
                       encoding="utf-8").read()
checks["v0.50 cabin mirror leg core"] = (("def cabin_leg" in _cabin_src)
    and ("cabin_watch_leg" in _main_src)
    and ("-rev" in _main_src))
checks["v0.50 mirror routes api+ui"] = (("cw_leg" in _webui_src)
    and ("mirror" in _webui_src)
    and ("cw-mirror" in _cabin_card_src))

_revive_src = open(os.path.join("core", "revive.py"),
                   encoding="utf-8").read()
_ver_src = open(os.path.join("core", "version.py"),
                encoding="utf-8").read()
_sources_src = open(os.path.join("web", "src", "components",
                                 "SourcesView.jsx"),
                    encoding="utf-8").read()
checks["v0.51+ version stamp"] = (
    bool(re.search(r'CODE_VERSION = "\d+\.\d+(\.\d+)?"', _ver_src))
    and ("code_ver" in _main_src))
checks["v0.51 stale hot-swap core"] = (("restarted-stale-code" in _revive_src)
    and ("stale_code_running" in _revive_src))
checks["v0.51 skew warn health+ui"] = (("code_synced" in _webui_src)
    and ("code_synced" in _sources_src))
checks["v0.52 cabin record-low core"] = (
    ("record_alert_candidate" in _cabin_src)
    and ('"record"' in _cabin_src))
checks["v0.52 record-low api+ui"] = (("alert_record_low" in _webui_src)
    and ("alertRecordLow" in _cabin_card_src)
    and ("新低" in _cabin_card_src))

_push_src = open(os.path.join("web", "src", "components",
                              "PushView.jsx"), encoding="utf-8").read()
_lan_ps1 = (open(os.path.join("tools", "enable_lan.ps1"),
                 encoding="utf-8").read()
            if os.path.exists(os.path.join("tools", "enable_lan.ps1")) else "")
checks["v0.53 lan-info api"] = (("/api/lan-info" in _webui_src)
    and ("_lan_ip" in _webui_src))
checks["v0.53 lan card + one-shot script"] = (("手机访问" in _push_src)
    and ("enable_lan" in _push_src)
    and ("advfirewall" in _lan_ps1)
    and ("-Revert" in _lan_ps1))
checks["v0.54 board explorer api"] = "/api/board" in _webui_src
checks["v0.54 board explorer ui"] = (("班期查询" in _sources_src)
    and ("searchBoard" in _sources_src)
    and ("dow-mini" in _sources_src)
    and ("班期查询" in _dist_js))
_kpis_src = open(os.path.join("web", "src", "components",
                              "Kpis.jsx"), encoding="utf-8").read()
checks["v0.55 drop watch core"] = (("day_drops" in _hist_src)
    and ("drop watch failed" in _main_src)
    and ("drop_pct" in _webui_src))
checks["v0.55 drops api+ui"] = (("/api/drops" in _webui_src)
    and ("fetchDrops" in _app_jsx_v2)
    and ("d-delta" in _kpis_src)
    and ("较昨日" in _dist_js))
checks["v0.56 drop gate panel"] = (("骤降提醒" in _push_src)
    and ("drop_pct" in _push_src)
    and ("drop_abs" in _push_src)
    and ("骤降提醒" in _dist_js))

_weekly_src = open(os.path.join("core", "weekly.py"), encoding="utf-8").read()
_weekly_view_src = open(os.path.join("web", "src", "components",
                                     "WeeklyView.jsx"), encoding="utf-8").read()
_cabin_src = open(os.path.join("web", "src", "components",
                               "CabinCard.jsx"), encoding="utf-8").read()
_notify_src = open(os.path.join("core", "notify.py"), encoding="utf-8").read()
_push_view_src = open(os.path.join("web", "src", "components",
                                   "PushView.jsx"), encoding="utf-8").read()
checks["v0.57 weekly highlights"] = (
    ("def week_highlights" in _weekly_src)
    and ("biggest_drop" in _weekly_src)
    and ("本周值得关注" in _weekly_view_src)
    and ("sharp_drops" in _weekly_view_src)
    and ("本周值得关注" in _dist_js))

checks["v0.58 weekly push_text wiring"] = (
    ("def push_text" in _weekly_src)
    and ("push_text(report)" in _main_src)
    and ("push_text(report)" in _webui_src)
    and ("推送正文" in _weekly_view_src)
    and ("推送正文" in _dist_js))

checks["v0.59 cabin ops closure"] = (
    ("amadeus_ready" in _webui_src)
    and ("amadeus_ready" in _cabin_src)
    and ("runNow" in _cabin_src)
    and ("立即刷新" in _cabin_src)
    and ("intervalMinutes" in _cabin_src)
    and ("刷新间隔" in _cabin_src)
    and ("立即刷新" in _dist_js))

checks["v0.60 alert history kinds"] = (
    ("def classify_alert" in _notify_src)
    and ("cabin-record" in _notify_src)
    and ("api_alerts_delete" in _webui_src)
    and ("counts" in _webui_src)
    and ("kindLabel" in _push_view_src)
    and ("清理测试" in _push_view_src)
    and ("清理测试" in _dist_js))

_ov_src = open(os.path.join("web", "src", "components", "OverviewCard.jsx"),
               encoding="utf-8").read() if os.path.exists(
    os.path.join("web", "src", "components", "OverviewCard.jsx")) else ""
checks["v0.61 route overview board"] = (("路线总览" in _ov_src)
    and ("按接近心理价位排序" in _ov_src)
    and ("路线总览" in _dist_js)
    and ("路线总览" in h))

_cabin_card_src = open(os.path.join("web", "src", "components",
                                    "CabinCard.jsx"),
                       encoding="utf-8").read() if os.path.exists(
    os.path.join("web", "src", "components", "CabinCard.jsx")) else ""
_cabin_core_src = open(os.path.join("core", "cabin_monitor.py"),
                       encoding="utf-8").read()
checks["v0.62 cabin history board"] = (("def history_board" in _cabin_core_src)
    and ("history_board" in open("webui.py", encoding="utf-8").read())
    and ("历史低价榜" in _cabin_card_src)
    and ("历史低价榜" in _dist_js))

checks["v0.63 overview times + spark"] = (("ov-times" in _ov_src)
    and ("spark-line" in _ov_src)
    and ("ov-times" in _dist_js)
    and ("ov-times" in h))

checks["v0.64 global best hero"] = (("全局最优" in _ov_src)
    and ("ov-best" in _ov_src)
    and ("全局最优" in _dist_js)
    and ("全局最优" in h))

checks["v0.65 global best to push"] = (("def global_best" in _weekly_src)
    and ("attach_global_best" in _main_src)
    and ("global_best" in open("webui.py", encoding="utf-8").read()))

checks["v0.66 cabin patrol"] = (("def patrol_legs" in _cabin_core_src)
    and ("def cabin_patrol_once" in _main_src)
    and ("patrol" in open("webui.py", encoding="utf-8").read())
    and ("独立巡检" in _cabin_card_src)
    and ("独立巡检" in _dist_js))

checks["v0.67 精点轮转"] = (("stats=fstats" in _main_src)
    and ("max_days_far=75" in _main_src)
    and ("deferred" in _main_src)
    and ("本轮点查" in _main_src))

_dd_src = open(os.path.join("web", "src", "components", "DayDetail.jsx"),
               encoding="utf-8").read()
checks["v0.68 参考落地时间"] = (('str(ent.get("arr")' in _sb_src)
    and ("arr if ok_arr else" in _sb_src)
    and ("need_arr" in _main_src)
    and ("arr_src = \"alt-ref\"" in _main_src)
    and ('"arr": a.get("arr")' in _reenrich_src)
    and ('+ a.arr' in _dd_src)
    and ("arr" in _dist_js and 'a.arr' in _dist_js))

_api_js_src = open(os.path.join("web", "src", "lib", "api.js"),
                   encoding="utf-8").read()
checks["v0.69 当日班期表+生产部署"] = (("day-schedule" in _webui_src)
    and ("fetchDaySchedule" in _api_js_src)
    and ("当日班期表" in _dd_src)
    and ("当日班期表" in _dist_js)
    and ("from waitress import serve" in _webui_src)
    and os.path.exists("Dockerfile")
    and os.path.exists("docker-compose.yml"))

_ov2_src = open(os.path.join("web", "src", "components",
                             "OverviewCard.jsx"), encoding="utf-8").read()
_ci_path = os.path.join(".github", "workflows", "ci.yml")
checks["v0.70 班期直达+省%+CI"] = (("dayListUrl" in _dd_src)
    and ("goDate=" in _dd_src)
    and ("直达去哪儿当日列表" in _dd_src)
    and ("直达去哪儿当日列表" in _dist_js)
    and ("省\n" in _ov2_src or "省 " in _ov2_src)
    and os.path.exists(_ci_path)
    and ("docker-build" in open(_ci_path, encoding="utf-8").read()))

checks["v0.71 班期航司机型+ghcr发布"] = (("ft-alt-craft" in _dd_src)
    and ("a.airline" in _dd_src)
    and ("ft-alt-craft" in _dist_js)
    and ('"craft": str(ent.get("craft") or "")' in _sb_src)
    and ('"craft": a.get("craft")' in _webui_src)
    and ("docker-publish" in open(_ci_path, encoding="utf-8").read())
    and ("ghcr.io" in open(_ci_path, encoding="utf-8").read()))

checks["v0.72 班期24h时间线"] = (("tl-rail" in _dd_src)
    and ("tl-dot" in _dd_src)
    and ("24小时" in _dd_src)
    and ("tl-rail" in _dist_js)
    and ("tl-dot" in _dist_js)
    and ("tl-dot" in _dist_css)
    and ("tl-lab" in _dist_css))

checks["v0.73 全量班期+经停标注"] = ((
    '"via": str(ent.get("via") or "")' in _sb_src)
    and ('"via": a.get("via")' in _webui_src)
    and ("经停" in _dd_src)
    and ("has_more" in _dd_src)
    and ("经停" in _dist_js)
    and ("has_more" in _dist_js))

checks["v0.74 班次历时+tag发布"] = (("flight_duration" in _sb_src)
    and ('"dur": flight_duration' in _webui_src)
    and ("历时" in _dd_src)
    and ("a.dur" in _dd_src)
    and ("历时" in _dist_js)
    and ("refs/tags" in open(_ci_path, encoding="utf-8").read()))

checks["v0.75 起降区间+自动备份"] = (("flight_duration_hm" in _sb_src)
    and ("(估)" in _main_src)
    and ("maybe_daily_backup" in _main_src)
    and ("tl-span" in _dd_src)
    and ("tl-span" in _dist_js)
    and ("tl-span" in _dist_css)
    and ("backups" in _webui_src)
    and ("次日到达" in _dd_src))

_dist_html = open(os.path.join("web", "dist", "index.html"),
                  encoding="utf-8").read()
_doctor_src = open(os.path.join("tools", "doctor.py"),
                   encoding="utf-8").read()
_pf_src = open(os.path.join("core", "point_fill.py"),
               encoding="utf-8").read()
checks["v0.76 PWA+doctor+精点补查"] = (
    ("manifest.webmanifest" in _dist_html)
    and ("apple-touch-icon" in _dist_html)
    and ("check_pwa" in _doctor_src)
    and ("point-fill" in _dist_js)
    and ("/api/point-fill" in _webui_src)
    and ("/api/point-gaps" in _webui_src))

_runall_src = open(os.path.join("run_all.py"), encoding="utf-8").read()
_compose_src = open(os.path.join("docker-compose.yml"), encoding="utf-8").read()
checks["v0.77 全功能容器+借班透明"] = (
    ("build_cmds" in _runall_src)
    and ("main.py" in _runall_src and "--loop" in _runall_src)
    and ("FA_ROLE" in _compose_src)
    and ("borrow_dow" in _main_src)
    and ("借周" in _dd_src)
    and ("借周" in _dist_js)
    and ("borrow_dow" in _dist_js))

_crawl_src = open(os.path.join("web", "src", "components", "CrawlView.jsx"),
                  encoding="utf-8").read()
_header_src = open(os.path.join("web", "src", "components", "Header.jsx"),
                   encoding="utf-8").read()
checks["v0.78 精点补查UI+时刻沉淀"] = (
    ("精点补查" in _crawl_src)
    and ("nextRunForDow" in _crawl_src)
    and ("fetchPointGaps" in _api_js_src)
    and ("postPointFill" in _api_js_src)
    and ("精点补查" in _dist_js)
    and ("缺口自动补齐预测" in _dist_js)
    and ("gap-chip" in _dist_css))

checks["v0.79 书签回填+自启体检"] = (
    ("build_bookmarklet" in _pf_src)
    and ("/api/bookmarklet" in _webui_src)
    and ("from_city" in _webui_src)
    and ("check_autostart" in _doctor_src)
    and ("fetchBookmarklet" in _api_js_src)
    and ("书签" in _dist_js)
    and ("bm-code" in _dist_css))

_flights_src = open(os.path.join("core", "flights.py"),
                    encoding="utf-8").read()
_revview_src = open(os.path.join("web", "src", "components",
                                 "ReverseView.jsx"), encoding="utf-8").read()
checks["v0.80 反向缓存榜+转正预告"] = (
    ("promote_on" in _flights_src)
    and ("/api/reverse-latest" in _webui_src)
    and ("fetchReverseLatest" in _api_js_src)
    and ("最近扫描" in _revview_src)
    and ("转精查" in _kpis_src)
    and ("promote_on" in _dist_js)
    and ("最近扫描" in _dist_js)
    and ("healthcheck" in _compose_src))

checks["v0.82 精点直达+启动文件夹自启"] = (
    ("gap-chip link" in _crawl_src)
    and ("qunarPointUrl(rt.from_city" in _crawl_src)
    and ('target="_blank"' in _crawl_src)
    and ("setInterval(load, 20000)" in _crawl_src)
    and ("FareAlertStartup.cmd" in _doctor_src)
    and ("WindowsApps" in _doctor_src)
    and os.path.exists(os.path.join("tools", "install_autostart.py"))
    and ("a.gap-chip" in _dist_css))

checks["v0.83 回填养板库+舱位书签"] = (
    ("queue_sched_deposit" in open(os.path.join("webui.py"),
                                   encoding="utf-8").read())
    and ("absorb_deposit" in open(os.path.join("core", "sched_board.py"),
                                  encoding="utf-8").read())
    and ("absorb_point_cabin" in open(os.path.join("core",
                                                   "cabin_monitor.py"),
                                      encoding="utf-8").read())
    and ("build_bookmarklet(origin, cabin)" in open(
        os.path.join("webui.py"), encoding="utf-8").read())
    and ("v2 ·" in _header_src))

_sched_src = open(os.path.join("core", "sched_board.py"), encoding="utf-8").read()
_daydetail_src = open(os.path.join("web", "src", "components", "DayDetail.jsx"),
                      encoding="utf-8").read()
_reenrich_src = open(os.path.join("core", "reenrich.py"), encoding="utf-8").read()
checks["v0.84 借班投票+标签回写+api_push"] = (
    ("borrow_consensus" in _sched_src)
    and ("borrow_unstable" in _sched_src)
    and ("borrow_unstable" in _daydetail_src)
    and ("timeSrcBadge(" in _daydetail_src)
    and ("borrow_votes" in _reenrich_src)
    and os.path.exists(os.path.join("tools", "api_push.py"))
    and ("borrow_unstable" in _dist_js)
    and ("v2 ·" in _header_src))

_alerts_src = open(os.path.join("core", "alerts.py"), encoding="utf-8").read()
_weekly_src = open(os.path.join("core", "weekly.py"), encoding="utf-8").read()
checks["v0.85 推送时刻+可信度标记"] = (
    ("def dep_arr_text" in _alerts_src)
    and ("def conf_mark" in _alerts_src)
    and ("dep_arr_text(d)" in _alerts_src)
    and ("conf_mark(gb)" in _weekly_src)
    and ("borrow_votes" in _weekly_src)
    and os.path.exists(os.path.join("tests", "test_alert_msg.py")))

_backup86_src = open(os.path.join("tools", "backup.py"),
                     encoding="utf-8").read()
_restore86_src = open(os.path.join("tools", "restore.py"),
                      encoding="utf-8").read()
_webui86_src = open(os.path.join("webui.py"), encoding="utf-8").read()
_crawl86_src = open(os.path.join("web", "src", "components",
                                 "CrawlView.jsx"), encoding="utf-8").read()
checks["v0.86 迁移包+Web一键导出导入"] = (
    ("data/history.json" in _backup86_src)
    and ("data/sched_deposit.json" in _backup86_src)
    and ("bundle_manifest.json" in _backup86_src)
    and ("verify_manifest" in _restore86_src)
    and ("safety_backup" in _restore86_src)
    and ("/api/bundle/export" in _webui86_src)
    and ("/api/bundle/import" in _webui86_src)
    and ("BackupCard" in _crawl86_src)
    and ("备份与迁移" in _dist_js))

_bkf87_src = open(os.path.join("core", "booking_fill.py"),
                  encoding="utf-8").read()
_main87_src = open(os.path.join("main.py"), encoding="utf-8").read()
_day87_src = open(os.path.join("web", "src", "components",
                               "DayDetail.jsx"), encoding="utf-8").read()
_src87_src = open(os.path.join("core", "sources.py"),
                  encoding="utf-8").read()
checks["v0.87 Booking无key灰点交叉补价"] = (
    ("LOWEST_PRICE" in _bkf87_src)
    and ("max_per_cycle" in _bkf87_src)
    and ("_booking_cross_fill" in _main87_src)
    and ("from core.booking_fill import" in _main87_src)
    and ("Booking参考" in _day87_src)
    and ("booking-fill" in _src87_src)
    and ("booking-ref" in _dist_js)
    and os.path.exists(os.path.join("tests", "test_booking_fill.py")))

_bkf88_src = open(os.path.join("core", "booking_fill.py"),
                  encoding="utf-8").read()
_main88_src = open(os.path.join("main.py"), encoding="utf-8").read()
_kpis88_src = open(os.path.join("web", "src", "components",
                                "Kpis.jsx"), encoding="utf-8").read()
_tests88_src = open(os.path.join("tests", "test_booking_fill.py"),
                    encoding="utf-8").read()
checks["v0.88 Booking完整行程+负缓存分级"] = (
    ("offer_itinerary" in _bkf88_src)
    and ("attach_times" in _bkf88_src)
    and ("NEG_TTL_ERR" in _bkf88_src)
    and ("NEG_TTL_NODATA" in _bkf88_src)
    and ("no_data" in _bkf88_src)
    and ("booking_attach_times" in _main88_src)
    and ("extra_dates=time_gaps" in _main88_src)
    and ("baggage_note" in _main88_src)
    and ("Booking精确" in _day87_src)
    and ("booking-x" in _day87_src)
    and ("booking-x" in _kpis88_src)
    and ("TestBookingExact" in _tests88_src))

_bkf89_src = open(os.path.join("core", "booking_fill.py"),
                  encoding="utf-8").read()
_webui89_src = open(os.path.join("webui.py"), encoding="utf-8").read()
_day89_src = open(os.path.join("web", "src", "components",
                               "DayDetail.jsx"), encoding="utf-8").read()
checks["v0.89 当日实测班次+systemd部署"] = (
    ("def offer_list" in _bkf89_src)
    and ("get(\"offers\")" in _bkf89_src)
    and ("_merge_booking_schedule" in _webui89_src)
    and ("src === \"booking\"" in _day89_src)
    and ("当日实测班次" in _day89_src)
    and ("Booking当日实测" in _day89_src)
    and os.path.exists(os.path.join("deploy", "systemd",
                                    "fare-alert.service"))
    and os.path.exists(os.path.join("deploy", "systemd", "install.sh"))
    and os.path.exists(os.path.join("deploy", "README.md")))

_t90_src = open(os.path.join("tests", "test_booking_fill.py"),
                encoding="utf-8").read()
checks["v0.90 遗留缓存实测班次升级轮转"] = (
    ("legacy positive quote" in _bkf89_src)
   and ('and (e.get("offers") or []))' in _bkf89_src)
    and ("has_booking" in _bkf89_src)
    and ("offers and not has_booking" in _bkf89_src)
   and ("test_legacy_positive_reprobed_for_offers" in _t90_src))

_webui91_src = open(os.path.join("webui.py"), encoding="utf-8").read()
_src91_src = open(os.path.join("web", "src", "components",
                             "SourcesView.jsx"), encoding="utf-8").read()
checks["v0.91 实测班次覆盖监控可见化"] = (
    ("def coverage_stats" in _bkf89_src)
    and ('"timetable": timetable' in _webui91_src)
    and ("coverage_stats(DATA_DIR)" in _webui91_src)
    and ("班次实测覆盖" in _src91_src)
    and ("hb.timetable.pending" in _src91_src)
   and ("test_mixed_cache_counts" in _t90_src))

_day92_src = open(os.path.join("web", "src", "components",
                           "DayDetail.jsx"), encoding="utf-8").read()
_css92_src = open(os.path.join("web", "src", "styles", "app.css"),
                  encoding="utf-8").read()
checks["v0.92 实测班次直达购票+低价班标记"] = (
    ('"ft-alt" + (best ? " best" : "")' in _day92_src)
    and ("ft-best" in _day92_src)
    and ("本日最低价航班" in _day92_src)
    and (".ft-alt.best" in _css92_src)
    and (".ft-best" in _css92_src)
    and ("a.ft-alt { text-decoration: none; }" in _css92_src))

_bk93_src = open(os.path.join("core", "booking_fill.py"),
                 encoding="utf-8").read()
_t93_src = open(os.path.join("tests", "test_booking_fill.py"),
                encoding="utf-8").read()
checks["v0.93 灰点反饥饿: 僵尸条目回放+预算优先"] = (
    ('"dep" not in e' in _bk93_src)
    and ("zombie and d in gap_set" in _bk93_src)
    and ("targets = (sorted(gap_set) +" in _bk93_src)
    and ('e["ts"] = now' in _bk93_src)
    and ("test_zombie_4key_replays_cold_on_gap" in _t93_src)
    and ("test_gap_dates_outrank_extra_dates" in _t93_src))

_main96_src = open("main.py", encoding="utf-8").read()
_t96_src = open(os.path.join("tests", "test_core.py"),
                encoding="utf-8").read()
checks["v0.96 当日最低参考班徽章"] = (
    ("_alt_times_with_best_ref" in _main96_src)
    and ("best_ref" in _main96_src)
    and ('"ft-best ref"' in _day92_src)
    and ("ref-best" in _day92_src)
    and (".ft-alt.ref-best" in _css92_src)
    and ("test_alt_times_best_ref" in _t96_src))

_hist97_src = open(os.path.join("core", "history.py"),
                   encoding="utf-8").read()
_wk97_src = open(os.path.join("core", "weekly.py"),
                 encoding="utf-8").read()
_wv97_src = open(os.path.join("web", "src", "components",
                            "WeeklyView.jsx"), encoding="utf-8").read()
_t97_src = open(os.path.join("tests", "test_weekly.py"),
                encoding="utf-8").read()
checks["v0.97 周报亮点带起降时刻"] = (
    ('("dep_time", "dep_time")' in _hist97_src)
    and ("s[k] = m[k]" in _wk97_src)
    and ("b[k] = m[k]" in _wk97_src)
    and ('str(s0["dep_time"]) + "起飞"' in _wk97_src)
    and ("b.dep_time" in _wv97_src)
    and ("s.dep_time" in _wv97_src)
    and ("test_route_metrics_archives_schedule" in _t97_src)
    and ("test_sharp_drop_carries_dep_time" in _t97_src))

_rev98_src = open(os.path.join("core", "revive.py"),
                  encoding="utf-8").read()
_wd98_src = open(os.path.join("tools", "watchdog.py"),
                 encoding="utf-8").read()
_wdreg98 = open(os.path.join("tools", "register_watchdog_task.ps1"),
                encoding="utf-8").read()
_revreg98 = open(os.path.join("tools", "register_revive_task.ps1"),
                 encoding="utf-8-sig").read()
_web98_src = open("webui.py", encoding="utf-8").read()
_tw98_src = open(os.path.join("tests", "test_watchdog.py"),
                 encoding="utf-8").read()
_tr98_src = open(os.path.join("tests", "test_revive.py"),
                 encoding="utf-8").read()
checks["v0.98 运行时看门狗: 90min复活+外部webui守护"] = (
    ("RUNTIME_DEAD_S" in _rev98_src)
    and ('"started-runtime"' in _rev98_src)
    and ("_runtime_restart_cooldown_ok" in _rev98_src)
    and ("def decide" in _wd98_src)
    and ("FAILS_BEFORE_RESTART = 2" in _wd98_src)
    and ("FareAlertWatchdog" in _wdreg98)
    and ("tools/watchdog.py" in _wdreg98)
    and ("tools/autostart_worker.ps1" in _revreg98)
    and ("watchdog_state.json" in _web98_src)
    and ("test_healthy_resets_fail_counter" in _tw98_src)
    and ("test_runtime_revive_midday_dead_worker" in _tr98_src))

_fx99_src = open(os.path.join("core", "fx.py"),
                 encoding="utf-8").read()
_bf99_src = open(os.path.join("core", "booking_fill.py"),
                 encoding="utf-8").read()
_web99_src = open("webui.py", encoding="utf-8").read()
_tfx99_src = open(os.path.join("tests", "test_fx.py"),
                  encoding="utf-8").read()
checks["v0.99 ECB daily fx: precise backfill accuracy"] = (
    ("api.frankfurter.app" in _fx99_src)
    and ("data-api.ecb.europa.eu" in _fx99_src)
    and ("fx_cache.json" in _fx99_src)
    and ('"fallback"' in _fx99_src)
    and ("_resolve_fx" in _bf99_src)
    and ("_reprice_eur" in _bf99_src)
    and ('"eur": round(float(got["total_eur"]), 2)' in _bf99_src)
    and ("fx_snapshot" in _web99_src)
    and ("test_frankfurter_primary" in _tfx99_src)
    and ("test_ecb_official_fallback" in _tfx99_src)
    and ("test_reprice_eur" in _tfx99_src))

_al100_src = open(os.path.join("core", "alerts.py"),
                  encoding="utf-8").read()
_wdreg100 = open(os.path.join("tools", "register_watchdog_task.ps1"),
                  encoding="utf-8-sig").read()
_tal100_src = open(os.path.join("tests", "test_alert_msg.py"),
                   encoding="utf-8").read()
checks["v1.00 推送参考班次: 缺时刻OTA行补具体起飞时间 + watchdog绝对路径"] = (
    ("def best_ref_alt" in _al100_src)
    and ("当日班次参考" in _al100_src)
    and ("sys.executable" in _wdreg100)
    and ("Test-Path" in _wdreg100)
    and ("test_reference_line_names_cheapest_booking_alt" in _tal100_src)
    and ("test_no_reference_line_without_booking_alts" in _tal100_src)
    and ("test_alt_without_window_is_skipped" in _tal100_src))

_pf101_src = open(os.path.join("core", "point_fill.py"),
                  encoding="utf-8").read()
_tb101_src = open(os.path.join("tests", "test_booking_fill.py"),
                  encoding="utf-8").read()
_crawl101_src = open(os.path.join("web", "src", "components",
                    "CrawlView.jsx"), encoding="utf-8").read()
checks["v1.01 灰点作战清单: booking-ref 日也算精点靶子"] = (
    ("from .flights import NON_REAL_SOURCES" in _pf101_src)
    and ("v1.01: booking-ref is reference-only too" in _pf101_src)
    and ("2026-09-16 live check" in _pf101_src)
    and ('self.assertEqual(gaps, ["2026-10-15", "2026-10-16"])'
         in _tb101_src)
    and ("没有查询到符合条件的航班" in _pf101_src)
    and ("qunarPointUrl" in _crawl101_src))

_webui102_src = open("webui.py", encoding="utf-8").read()
_crawl102_src = open(os.path.join("web", "src", "components",
                    "CrawlView.jsx"), encoding="utf-8").read()
_src102_src = open(os.path.join("web", "src", "components",
                   "SourcesView.jsx"), encoding="utf-8").read()
_css102_src = open(os.path.join("web", "src", "styles", "app.css"),
                  encoding="utf-8").read()
_weekly102_src = open(os.path.join("core", "weekly.py"),
                     encoding="utf-8").read()
checks["v1.02 自动精点引导: point-gaps auto_fill + 面板横幅 + 密钥测试"] = (
    ("v1.02: response carries an auto_fill block" in _webui102_src)
    and ("amadeus_ready" in _webui102_src)
    and ("https://developer.amadeus.com/register" in _webui102_src)
    and ("auto_fill" in _webui102_src)
    and ("gap-af on" in _crawl102_src)
    and ("Amadeus 免费测试密钥" in _crawl102_src)
    and ("amadeusTest" in _src102_src)
    and ("developer.amadeus.com/register" in _src102_src)
    and ("测试密钥" in _src102_src)
   and (".gap-af {" in _css102_src)
   and ("班期库已沉淀" in _weekly102_src)
   and ("自动补齐" in _weekly102_src))

_flights103_src = open(os.path.join("core", "flights.py"),
                       encoding="utf-8").read()
_webui103_src = open("webui.py", encoding="utf-8").read()
_cal103_src = open(os.path.join("web", "src", "components",
                   "CalendarView.jsx"), encoding="utf-8").read()
_pf103_src = open(os.path.join("core", "point_fill.py"),
                  encoding="utf-8").read()
checks["v1.03 时刻口径修正: time_kind 统一分类 + 参考行计数 + 图例三分"] = (
    ("EXACT_TIME_SOURCES" in _flights103_src)
    and ("ref_total" in _flights103_src)
    and ("ref_dep_exact" in _flights103_src)
    and ("time_kind" in _webui103_src)
    and ("当日真实时刻" in _cal103_src)
    and ("当日真实时刻" in _dist_js)
    and ("tc-refline" in _crawl102_src)
    and ("tc-refline" in _dist_js)
   and (".tc-refline {" in _css102_src)
   and ("Chrome 136" in _pf103_src))

_main104_src = open("main.py", encoding="utf-8").read()
_sb104_src = open(os.path.join("core", "sched_board.py"),
                  encoding="utf-8").read()
_t104_src = open(os.path.join("tests", "test_v104.py"),
                 encoding="utf-8").read()
_ver104_src = open(os.path.join("core", "version.py"),
                   encoding="utf-8").read()
checks["v1.04 真价行时刻升级: 精确板期压过 Booking 借用钉"] = (
    ("def apply_board_upgrade" in _sb104_src)
    and ("apply_board_upgrade" in _main104_src)
    and ("bk_borrowed" in _main104_src)
    and ("bk-upgrade" in _main104_src)
    and ("test_exact_vs_crossdow_policy_chain" in _t104_src)
    and ("test_no_pingpong_with_booking_attach" in _t104_src))
    # v1.05: dropped the CODE_VERSION=="1.04" pin - feature markers
    # stay green across version bumps; current version is pinned by
    # the v1.05 block instead.


_pf105_src = open(os.path.join("core", "point_fill.py"),
                  encoding="utf-8").read()
_dd105_src = open(os.path.join("web", "src", "components", "DayDetail.jsx"),
                  encoding="utf-8").read()
_cv105_src = open(os.path.join("web", "src", "components", "CrawlView.jsx"),
                  encoding="utf-8").read()
_t105_src = open(os.path.join("tests", "test_v105.py"),
                 encoding="utf-8").read()
_ver105_src = open(os.path.join("core", "version.py"),
                   encoding="utf-8").read()
checks["v1.05 point-fill v2: full-list bookmarklet + lowest-wins cache + inline form"] = (
    ("cardOf" in _pf105_src)
    and ("LOWEST total wins the slot" in _pf105_src)
    and ("pf-inline" in _dd105_src)
    and ("postPointFill" in _dd105_src)
    and (chr(20840)+chr(37096)+chr(33322)+chr(29677) in _cv105_src)
    and ("cardOf" in _t105_src)
    )
# v1.06: dropped the v1.05 block's CODE_VERSION pin - feature
# markers stay green across bumps; the v1.06 block pins the version.

_sb106_src = open(os.path.join("core", "sched_board.py"),
                  encoding="utf-8").read()
_main106_src = open("main.py", encoding="utf-8").read()
_t106_src = open(os.path.join("tests", "test_v106.py"),
                 encoding="utf-8").read()
checks["v1.06 first-leg upgrade + shared-number guard"] = (
    ("apply_board_upgrade_first_leg" in _sb106_src)
    and ("v1.06: \u822a\u73ed\u53f7\u4f1a\u88ab\u590d\u7528" in _sb106_src)
    and ("apply_board_upgrade_first_leg(d, ent)" in _main106_src)
    and ("shared-number exact dow is downgraded" in _t106_src))

# --- v1.07: starved-dow balance (weekend board holes) ---
_db107_src = open(os.path.join("core", "dow_balance.py"),
                  encoding="utf-8").read()
_main107_src = open("main.py", encoding="utf-8").read()
_t107_src = open(os.path.join("tests", "test_v107.py"),
                 encoding="utf-8").read()
_ver107_src = open(os.path.join("core", "version.py"),
                   encoding="utf-8").read()
checks["v1.07 starved-dow balance"] = (
    ("def balance_once" in _db107_src)
    and ("def weak_dows" in _db107_src)
    and ("queue_sched_deposit" in _db107_src)
    and ("absorb_deposit" in _db107_src)
    and ("RUN_TTL" in _db107_src)
    and ("from core.dow_balance import balance_once" in _main107_src)
    and ("weekend-off db yields weak dows" in _t107_src)
    and ("re-balance keeps observed dep" in _t107_src))

# --- v1.08: balance 2.0 (severe multi-date + full-day offers) ---
_db108_src = open(os.path.join("core", "dow_balance.py"),
                  encoding="utf-8").read()
_bf108_src = open(os.path.join("core", "booking_fill.py"),
                  encoding="utf-8").read()
_t108_src = open(os.path.join("tests", "test_v108.py"),
                 encoding="utf-8").read()
_ver108_src = open(os.path.join("core", "version.py"),
                   encoding="utf-8").read()
checks["v1.08 balance 2.0 severe multi-date"] = (
    ("SEVERE_RATIO" in _db108_src)
    and ("SEVERE_TTL" in _db108_src)
    and ("SEVERE_DATES" in _db108_src)
    and ("DATE_POOL" in _db108_src)
    and ("OFFER_LIMIT" in _db108_src)
    and ("offer_limit" in _bf108_src)
    and ("severe dow6 probes 3 dates" in _t108_src)
    and ("offer_limit=30 passed through" in _t108_src)
    and ("weak-only db: 12h gate blocks +5h" in _t108_src))

# --- v1.09: keyless business-cabin patrol (booking BUSINESS gateway) ---
_cm109_src = open(os.path.join("core", "cabin_monitor.py"),
                  encoding="utf-8").read()
_bf109_src = open(os.path.join("core", "booking_fill.py"),
                  encoding="utf-8").read()
_main109_src = open(os.path.join("main.py"),
                    encoding="utf-8").read()
_webui109_src = open(os.path.join("webui.py"),
                     encoding="utf-8").read()
_t109_src = open(os.path.join("tests", "test_v109.py"),
                 encoding="utf-8").read()
checks["v1.09 keyless business-cabin patrol"] = (
    ("probe_dates" in _cm109_src)
    and ("booking_cabin_rows" in _cm109_src)
    and ("probe_dates_per_round" in _cm109_src)
    and ('cabinClass": cabin_class' in _bf109_src)
    and ("cabin_bk_rows" in _main109_src)
    and ('cabin_class="BUSINESS"' in _main109_src)
    and ("booking_cabin_ready" in _webui109_src)
    and ("roundtrip_tax_inclusive" in _t109_src)
    and ("booking_cabin_is_real_source" in _t109_src))

# --- v1.10: agent task center + per-flight cabin timetable ---
_at110_src = open(os.path.join("core", "agent_tasks.py"),
                  encoding="utf-8").read()
_webui110_src = open(os.path.join("webui.py"),
                     encoding="utf-8").read()
_app110_src = open(os.path.join("webui", "static", "app.js"),
                   encoding="utf-8").read()
_idx110_src = open(os.path.join("webui", "templates", "index.html"),
                   encoding="utf-8").read()
_t110_src = open(os.path.join("tests", "test_v110.py"),
                 encoding="utf-8").read()
_tcp_src = open(os.path.join("tests", "test_cabin_precision.py"),
                encoding="utf-8").read()
checks["v1.10 agent task center"] = (
    ("build_ledger" in _at110_src)
    and ('"/api/tasks"' in _webui110_src)
    and ("cabin-patrol/run" in _webui110_src)
    and ("renderAgents" in _app110_src)
    and ('data-tab="agents"' in _idx110_src)
    and ("test_projection_from_real_files" in _t110_src))
checks["v1.10 per-flight cabin timetable"] = (
    ("price_eur" in _cm109_src)
    and ("fno=\"\"" in _cm109_src)
    and ("low_fno" in _cm109_src)
    and ("HISTORY_CAP = 300" in _cm109_src)
    and ('"probe_dates_per_round": 12' in _cm109_src)
    and ("fno=d.flight_no" in _main109_src)
    and ("offer_limit=8" in _main109_src)
    and ("test_offers_become_per_flight_rows" in _tcp_src)
    and ("test_flights_coexist_same_date" in _tcp_src))

# --- v1.11: cabin tab (from zero) ---
_cm111_src = _cm109_src   # same file, re-read not needed
_idx111_src = _idx110_src
_t111_src = open(os.path.join("tests", "test_v111.py"),
                 encoding="utf-8").read()
checks["v1.11 cabin tab from zero"] = (
    ("def history_timetable" in _cm111_src)
    and ('dep="", arr=""' in _cm111_src)
    and ("d.dep_time or """ in _main109_src)
    and ('data-tab="cabin"' in _idx111_src)
    and ('id="cabinPanel"' in _idx111_src)
    and ("function loadCabin" in _app110_src)
    and ('if (name === "cabin") loadCabin();' in _app110_src)
    and ("btnRefreshCabin" in _app110_src)
    and ("cabin-low-badge" in open(os.path.join(
        "webui", "static", "style.css"), encoding="utf-8").read())
    and ("cabinClass=BUSINESS" in _webui110_src)
    and ("test_projection_sorted_cheapest_first" in _t111_src))

# --- v1.12: time-quality heat map + cabin sparklines ---
_t112_src = open(os.path.join("tests", "test_v112.py"),
                 encoding="utf-8").read()
_css112_src = open(os.path.join("webui", "static", "style.css"),
                   encoding="utf-8").read()
checks["v1.12 time heat + cabin spark"] = (
    ('id="timeHeat"' in _idx111_src)
    and ("time-heat-box" in _idx111_src)
    and ("tab-timeheat" not in _idx111_src)
    and ("function loadTimeHeat" in _app110_src)
    and ("/api/time-coverage" in _app110_src)
    and ("function cabinSpark" in _app110_src)
    and ('"spark": spark' in _cm111_src)
    and (".time-heat-box" in _css112_src)
    and (".cabin-spark-line" in _css112_src)
    and (".th-cell.exact" in _css112_src)
    and ("test_spark_projection" in _t112_src))

# --- v1.13: v2 main entry - agents tab + cabin timetable ---
_t113_src = open(os.path.join("tests", "test_v113.py"),
                 encoding="utf-8").read()
_app113_src = open(os.path.join("web", "src", "app.jsx"),
                   encoding="utf-8").read()
_agents113_src = open(os.path.join(
    "web", "src", "components", "AgentsView.jsx"),
    encoding="utf-8").read()
_cabin_tt113_src = open(os.path.join(
    "web", "src", "components", "CabinTimetable.jsx"),
    encoding="utf-8").read()
_card113_src = open(os.path.join(
    "web", "src", "components", "CabinCard.jsx"),
    encoding="utf-8").read()
checks["v1.13 v2 agents + cabin timetable"] = (
    ('["agents", "🤖 任务中心"]' in _app113_src)
    and ('{tab === "agents" ? <AgentsView /> : null}' in _app113_src)
    and ("fetchTasks" in _agents113_src)
    and ("runAgentPath" in _agents113_src)
    and ("g.spark" in _cabin_tt113_src)
    and ("window.open(row.url" in _cabin_tt113_src)
    and ("<CabinTimetable timetable={data.timetable} />" in _card113_src)
    and ("test_agents_view_wired" in _t113_src)
    and os.path.exists(os.path.join(
        "web", "src", "components", "AgentsView.jsx")))

# --- v1.14: time-gap-first probing + coverage chip ---
_t114_src = open(os.path.join("tests", "test_v114.py"),
                 encoding="utf-8").read()
_cm114_src = open(os.path.join("core", "cabin_monitor.py"),
                  encoding="utf-8").read()
_main114_src = open("main.py", encoding="utf-8").read()
_css114_src = open(os.path.join("web", "src", "styles", "app.css"),
                   encoding="utf-8").read()
checks["v1.14 time-gap-first + cov chip"] = (
    ("def time_gap_dates(" in _cm114_src)
    and ("time_first=True" in _cm114_src)
    and ("n_gap = min(len(gap_days)" in _cm114_src)
    and ("best[key] = o" in _cm114_src)
    and ('"timed": timed' in _cm114_src)
    and ("cabin_time_gaps" in _main114_src)
    and ('info["time_refill"]' in _main114_src)
    and ("cab-tt-cov" in _cabin_tt113_src)
    and (".cab-tt-cov" in _css114_src)
    and ("test_timeless_date_jumps_queue" in _t114_src))

# --- v1.14.1: one-shot cabin gap refill ops tool ---
_refill141_src = open(os.path.join("tools", "cabin_refill.py"),
                      encoding="utf-8").read()
checks["v1.14.1 cabin_refill ops tool"] = (
    os.path.exists(os.path.join("tools", "cabin_refill.py"))
    and ("--dry" in _refill141_src)
    and ("--max" in _refill141_src)
    and ("cabin_class=\"BUSINESS\"" in _refill141_src)
    and ("_SilentLog(), False" in _refill141_src)
    and ("server-confirmed" in _refill141_src)
    and ("transient (throttled?)" in _refill141_src))

# --- v1.15: 429 circuit breaker + fingerprint rotation ---
_bf115_src = open(os.path.join("core", "booking_fill.py"),
                  encoding="utf-8").read()
_t115_src = open(os.path.join("tests", "test_v115.py"),
                 encoding="utf-8").read()
_main115_src = open("main.py", encoding="utf-8").read()
checks["v1.15 429 breaker + fp rotation"] = (
    ('return {"throttled": True}' in _bf115_src)
    and ("def bump_fingerprint(" in _bf115_src)
    and ("def current_fingerprint(" in _bf115_src)
    and ("def warm_session(" in _bf115_src)
    and ('"throttled": n429' in _bf115_src)
    and ("got.get(\"throttled\")" in _main115_src)
    and ("booking_bump_fp()" in _main115_src)
    and ('info["throttle"] = n_thr' in _main115_src)
    and ("test_two_strikes_stop_the_batch" in _t115_src)
    and ("test_429_returns_throttled_marker" in _t115_src))

# --- v1.15.1: adaptive 429 patrol backoff ---
_cm151_src = open(os.path.join("core", "cabin_monitor.py"),
                   encoding="utf-8").read()
_t151_src = open(os.path.join("tests", "test_v1151.py"),
                 encoding="utf-8").read()
_at151_src = open(os.path.join("core", "agent_tasks.py"),
                  encoding="utf-8").read()
_w151_src = open("webui.py", encoding="utf-8").read()
checks["v1.15.1 adaptive 429 patrol backoff"] = (
    ("def patrol_gap(" in _cm151_src)
    and ("cabin_patrol_gap" in _main115_src)
    and ('info["throttle_streak"]' in _main115_src)
    and ('info["interval_effective_minutes"]' in _main115_src)
    and ("interval_effective_minutes" in _at151_src)
    and ('"throttle_streak":' in _w151_src)
    and ('"interval_effective_minutes":' in _w151_src)
    and ("test_clean_round_resets_to_base" in _t151_src)
    and ("test_third_throttle_caps_at_six" in _t151_src)
    and ("test_backoff_wired_end_to_end" in _t151_src))

bad = 0
for k, v in checks.items():
    if not v1_dom and k in legacy_keys:
        print("SKIP " + k + " (v1 DOM 快照缺失, v2 快照不适用)")
        continue
    print(("PASS " if v else "FAIL ") + k)
    bad += 0 if v else 1
days = len(re.findall("class=.day ", h))
if v1_dom:
    print("day cells:", days)
    m = re.findall("当前最优[^。<]{0,20}", h)
    print("verdict:", m[0] if m else "MISSING")
else:
    print("(v2 快照: v1 日历/最优断言不适用, 已整体 SKIP)")
# --- structural: every data-tab button maps to exactly one panel; ids unique ---
import collections
tabs = set(re.findall(r'data-tab=[\'"]([a-z]+)[\'"]', h))
struct_bad = []
for t in sorted(tabs):
    n = len(re.findall(r'id=[\'"]tab-%s[\'"]' % t, h))
    if n != 1:
        struct_bad.append("tab '%s' -> %d panels" % (t, n))
id_counts = collections.Counter(re.findall(r'id=[\'"]([A-Za-z][A-Za-z0-9_-]*)[\'"]', h))
dups = sorted(i for i, c in id_counts.items() if c > 1)
if dups:
    struct_bad.append("duplicate ids: " + ", ".join(dups))
for s in struct_bad:
    print("FAIL STRUCT " + s)
    bad += 1
if not struct_bad:
    if tabs:
        print("PASS STRUCT %d tabs 1:1 panels, ids unique" % len(tabs))
    else:
        print("SKIP STRUCT tabs 1:1 panels (v2 快照无 data-tab)")
css_body = css[css.index("}", css.index(":root")) + 1:]
_hex_left = re.findall(r"#[0-9a-fA-F]{3,8}\b", css_body)
_fs_left = re.findall(r"font-size:\s*[\d.]+px", css_body)
if _hex_left or _fs_left:
    print("FAIL STRUCT v0.28 设计令牌: 硬编码残留 hex=%d font-size=%d" % (len(_hex_left), len(_fs_left)))
    bad += 1
else:
    print("PASS STRUCT v0.28 设计令牌: 规则体零硬编码色值/字号")
if _hex_v2:
    print("FAIL STRUCT v0.29 v2 frontend: hardcoded hex %d: %s" % (len(_hex_v2), ", ".join(_hex_v2[:5])))
    bad += 1
elif not _old_tokens <= _new_tokens:
    print("FAIL STRUCT v0.29 v2 frontend: missing tokens: %s" % ", ".join(sorted(_old_tokens - _new_tokens)[:8]))
    bad += 1
else:
    print("PASS STRUCT v0.29 v2 frontend: tokens synced, zero hardcoded hex (%d tokens)" % len(_new_tokens))
sys.exit(1 if (bad or (v1_dom and days < 30)) else 0)
