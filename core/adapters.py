# -*- coding: utf-8 -*-
"""M5 数据源适配器插件层.

目标(DoD): 新数据源只实现本文件接口 + 通过 tests/test_adapters.py 夹具
一致性测试, 不需要改 crawl/travel/reverse 等核心编排代码.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from .models import FlightDeal


REGISTRY = {}  # id -> adapter class


def register(cls):
    """Class decorator: 注册适配器(重复 id 后者覆盖前者, 便于测试替换)."""
    REGISTRY[cls.id] = cls
    return cls


@dataclass
class FetchQuery:
    """一次日历查询的统一入参(与具体数据源无关)."""
    from_city: str
    to_city: str
    date_from: str          # YYYY-MM-DD
    date_to: str
    tax_cfg: dict = field(default_factory=dict)   # 燃油/机建等税费配置
    ama_cfg: dict = field(default_factory=dict)   # amadeus 密钥配置
    data_dir: str = ""                            # 缓存目录(amadeus token 等)


class BaseAdapter:
    id = ""                    # 与 SOURCE_REGISTRY 对齐
    kind = "flight"            # flight | train
    name = ""
    status = "可用"            # 可用 | 需配置 | 规划中
    priority = 100             # 越小越先尝试

    def is_configured(self, config):
        """返回 (是否可用, 缺配置时的中文提示). 默认无条件可用."""
        return True, ""

    def fetch(self, session, net_cfg, config, q):
        raise NotImplementedError


class FlightSourceAdapter(BaseAdapter):
    """机票日历源: 返回 list[FlightDeal], 按 (bare_price, date) 升序."""
    kind = "flight"


class TrainSourceAdapter(BaseAdapter):
    """车票查询源: 返回 list[TrainFare]."""
    kind = "train"


# ---------------------------------------------------------------- 现有源包装

@register
class QunarCalendarAdapter(FlightSourceAdapter):
    id = "qunar-calendar"
    name = "去哪儿低价日历"
    priority = 10

    def fetch(self, session, net_cfg, config, q):
        from . import flights
        return flights.fetch_calendar(session, net_cfg, q.from_city,
                                      q.to_city, q.date_from, q.date_to)


@register
class QunarIntlPromoAdapter(FlightSourceAdapter):
    id = "qunar-intl"
    name = "去哪儿国际特价日历"
    priority = 20

    def fetch(self, session, net_cfg, config, q):
        from . import flights
        return flights.fetch_intl_promo_calendar(
            session, net_cfg, q.from_city, q.to_city,
            q.date_from, q.date_to, q.tax_cfg)


@register
class AmadeusIntlAdapter(FlightSourceAdapter):
    id = "amadeus-intl"
    name = "Amadeus国际低价日历"
    priority = 30

    def is_configured(self, config):
        key = ((config.get("amadeus") or {}).get("api_key") or "").strip()
        sec = ((config.get("amadeus") or {}).get("api_secret") or "").strip()
        if not key or not sec:
            return False, "Amadeus 需在「国际航班」页配置 api_key/api_secret"
        return True, ""

    def fetch(self, session, net_cfg, config, q):
        from . import intl
        deals = intl.fetch_intl_calendar(
            session, net_cfg, q.ama_cfg or config.get("amadeus") or {},
            q.tax_cfg, intl.city_iata(q.from_city),
            intl.city_iata(q.to_city), q.date_from, q.date_to, q.data_dir)
        return deals


# ---------------------------------------------------------------- 一致性校验

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_deals(deals, adapter_id, date_from, date_to):
    """夹具一致性校验: 返回错误列表(空=通过). 测试与运行时共用."""
    errors = []
    if not isinstance(deals, list):
        return ["%s: fetch 必须返回 list, 得到 %s" % (adapter_id, type(deals).__name__)]
    for i, d in enumerate(deals):
        if not isinstance(d, FlightDeal):
            errors.append("%s[%d]: 必须是 FlightDeal" % (adapter_id, i))
            continue
        if not _DATE_RE.match(d.date or ""):
            errors.append("%s[%d]: 日期格式需 YYYY-MM-DD, 得到 %r" % (adapter_id, i, d.date))
        elif not (date_from <= d.date <= date_to):
            errors.append("%s[%d]: 日期 %s 超出查询区间 [%s, %s]"
                          % (adapter_id, i, d.date, date_from, date_to))
        if not isinstance(d.bare_price, (int, float)) or d.bare_price <= 0:
            errors.append("%s[%d]: 价格需为正数, 得到 %r" % (adapter_id, i, d.bare_price))
        if d.source != adapter_id:
            errors.append("%s[%d]: source 字段 %r 与适配器 id 不一致" % (adapter_id, i, d.source))
    keys = [(d.bare_price, d.date) for d in deals if isinstance(d, FlightDeal)]
    if keys != sorted(keys):
        errors.append("%s: 结果需按 (bare_price, date) 升序" % adapter_id)
    return errors


# ---------------------------------------------------------------- 回放夹具

class ReplayAdapter(FlightSourceAdapter):
    """离线回放适配器: 读取 JSON 夹具模拟一个数据源(测试/演示用)."""
    id = "replay"
    name = "回放夹具源"

    def __init__(self, fixture_path):
        self.fixture_path = fixture_path
        with open(fixture_path, encoding="utf-8") as f:
            fx = json.load(f)
        self.id = fx.get("id", "replay")
        self.name = fx.get("name", "回放夹具源")
        self._deals = fx.get("deals", [])

    def fetch(self, session, net_cfg, config, q):
        out = []
        for e in self._deals:
            if not (q.date_from <= e["date"] <= q.date_to):
                continue
            out.append(FlightDeal(
                date=e["date"], bare_price=float(e["price"]),
                flight_no=e.get("flight_no", ""), source=self.id,
                url=e.get("url", ""),
                dep_time=e.get("dep_time", ""), arr_time=e.get("arr_time", ""),
                duration_text=e.get("duration_text", "")))
        out.sort(key=lambda x: (x.bare_price, x.date))
        return out


def fixture_dir():
    return os.path.join(os.path.dirname(__file__), "..", "tests",
                        "fixtures", "adapters")
