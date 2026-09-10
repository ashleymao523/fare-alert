# -*- coding: utf-8 -*-
"""Natural-language intent -> route config (pure functions, no network).

MCP watch_add 的解析后端:把"五一杭州飞成都800以内"这类一句话
解析成 route 配置。只做规则解析,不联网;解析不到的字段留 None
并写进 ambiguous,由调用方(Agent/用户)追问补齐。
"""
import datetime as dt
import re

from core.cities import CITIES

_NAME2PY = {c["name"]: c["pinyin"] for c in CITIES}

# 浮动节假日近两年固定日期(每年需人工更新;过期年份解析时自动顺延到下一年并提示)
HOLIDAYS = {
    "元旦": (1, 1),
    "清明": (4, 4),
    "五一": (5, 1),
    "端午": (5, 31),
    "中秋": (10, 6),
    "国庆": (10, 1),
    "春节": (2, 17),
}
_FLOATING = {"清明", "端午", "中秋", "春节"}  # 农历/节气浮动,日期为近似

_NUM = r"(\d{2,5})"


def _find_cities(text):
    """返回 [(pos, city_name)] 按出现位置排序。"""
    hits = []
    for name in _NAME2PY:
        pos = text.find(name)
        if pos >= 0:
            hits.append((pos, name))
    hits.sort()
    return [name for _, name in hits]


def _strip_dirs(city):
    return re.sub(r"^[从去到往飞]+|[的]?出发$|到达$", "", city)


def _parse_cities(text):
    cities = _find_cities(text)
    if len(cities) < 2:
        return None, None
    # "飞"分隔符决定方向: X飞Y -> X->Y
    m = re.search(r"飞", text)
    if m:
        left = [c for c in cities if text.find(c) < m.start()]
        right = [c for c in cities if text.find(c) > m.start()]
        if left and right:
            return left[0], right[0]
    # 方向词: "从X出发..." 定 from, "...去/到/往Y" 定 to
    frm = to = None
    m = re.search(r"从(.+?)(?:出发|$)", text)
    if m:
        frm = next((c for c in cities if m.group(1).find(c) >= 0), None)
    m = re.search(r"[去到往](.+?)$", text)
    if m:
        to = next((c for c in cities if m.group(1).find(c) >= 0), None)
    if frm and to and frm != to:
        return frm, to
    if frm or to:
        other = [c for c in cities if c not in (frm, to)]
        if frm and other:
            return frm, other[0]
        if to and other:
            return other[0], to
    return cities[0], cities[1]


def _next_occurrence(month, day, today=None):
    """今年该日期已过则取明年。"""
    today = today or dt.date.today()
    try:
        d = dt.date(today.year, month, day)
    except ValueError:
        return None
    if d < today:
        d = dt.date(today.year + 1, month, day)
    return d.isoformat()


def parse_intent(text, today=None):
    """一句话 -> 路线配置草稿。never raises; unknown fields -> None + ambiguous."""
    out = {
        "ok": True, "from_city": None, "to_city": None,
        "threshold_total": None, "window_days": 60, "date_from": None,
        "trip_type": "oneway", "intl": False, "route_id": None,
        "ambiguous": [],
    }
    text = (text or "").strip()
    if not text:
        out["ok"] = False
        out["ambiguous"].append("空输入")
        return out

    # --- 城市对 ---
    frm, to = _parse_cities(text)
    if frm and to:
        out["from_city"], out["to_city"] = frm, to
        out["route_id"] = "%s-%s" % (_NAME2PY[frm], _NAME2PY[to])
    else:
        out["ok"] = False
        out["ambiguous"].append("城市对未识别(需含出发/到达两个城市,如'杭州飞成都')")

    # --- 阈值: 800以内 / 低于800 / 预算800 / 800元 ---
    for pat in (r"低于\s*" + _NUM, r"预算\s*" + _NUM,
                _NUM + r"\s*元?(?:以内|以下|之内|内)", _NUM + r"\s*元"):
        m = re.search(pat, text)
        if m:
            out["threshold_total"] = int(m.group(1))
            break
    if out["threshold_total"] is None:
        out["ambiguous"].append("阈值未识别(如'800以内');可稍后在网页端设置")

    # --- 日期 ---
    m = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", text)
    if m:
        out["date_from"] = _next_occurrence(int(m.group(1)), int(m.group(2)), today)
        if out["date_from"] is None:
            out["ambiguous"].append("月日无效(如'5月1日')")
    else:
        for name, (mo, dy) in HOLIDAYS.items():
            if name in text:
                out["date_from"] = _next_occurrence(mo, dy, today)
                if name in _FLOATING:
                    out["ambiguous"].append("%s按近似日期%s解析,农历浮动请确认" % (name, out["date_from"]))
                break
    m = re.search(r"(\d{1,3})\s*天(?:以内|内|之内)?", text)
    if m and int(m.group(1)) <= 365:
        out["window_days"] = int(m.group(1))

    # --- 往返/国际 ---
    if "往返" in text:
        out["trip_type"] = "roundtrip"
    if "国际" in text:
        out["intl"] = True
    return out


def window_from_date(intent, today=None):
    """有 date_from 时把窗口拉长到覆盖出发日起 window_days 天(含当天,无off-by-one)。
    返回最终 window_days;intent 无 date_from 时原样返回。"""
    if not intent.get("date_from"):
        return intent.get("window_days", 60)
    today = today or dt.date.today()
    start = dt.date.fromisoformat(intent["date_from"])
    lead = (start - today).days
    return max(1, lead + intent.get("window_days", 60) - 1)
