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
appjs = open(os.path.join("webui", "static", "app.js"), encoding="utf-8").read()
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
}
bad = 0
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
    bad += 0 if v else 1
days = len(re.findall("class=.day ", h))
print("day cells:", days)
m = re.findall("当前最优[^。<]{0,20}", h)
print("verdict:", m[0] if m else "MISSING")
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
    print("PASS STRUCT %d tabs 1:1 panels, ids unique" % len(tabs))
sys.exit(1 if (bad or days < 30) else 0)
