# -*- coding: utf-8 -*-
"""Data models."""
from dataclasses import dataclass, field


@dataclass
class FlightDeal:
    date: str
    bare_price: float
    flight_no: str
    source: str = "qunar-calendar"
    url: str = ""
    dep_time: str = ""        # 起飞时刻(当前源未提供, 留给后续数据源)
    arr_time: str = ""        # 到达时刻
    arr_est: str = ""         # 落地估算(hh:mm, 大圆估): 独立字段, 不与真实时刻混源
    duration_text: str = ""   # 飞行时长
    time_src: str = ""        # 时刻来源: ""=无 | amadeus | airport-board | airport-board-x
    dep_src: str = ""         # v0.22 按字段来源: dep 时刻来源(经停时与 arr 可能不同源)
    arr_src: str = ""         # v0.22 按字段来源: arr 时刻来源
    ref_offset: int = 0       # nearby-ref: 距参考价日期的天数(0=非参考价)
    alt_times: list = field(default_factory=list)  # v0.26 无号deal参考班次 [{no,dep,exact}]
    stop_kind: str = ""       # v0.33 中转/经停透明化: ""=无 | transfer=中转(联程首段) | via=经停
    stop_city: str = ""       # 中转城市(首段 to)或经停城市(ent.via)
    stop_arr: str = ""        # 到达中转/经停城市的时刻(首段 arr 或 via_arr)

    @property
    def airline_code(self):
        return self.flight_no[:2].upper() if len(self.flight_no) >= 2 else ""


@dataclass
class TrainFare:
    pair: str
    train_code: str
    from_station: str
    to_station: str
    dep_time: str
    arr_time: str
    duration_text: str
    seats: dict = field(default_factory=dict)
    url: str = ""             # 12306 预填查询链接

    @property
    def train_type(self):
        return self.train_code[0] if self.train_code else ""

    @property
    def second_class(self):
        return self.seats.get("二等座")

    @property
    def student_second_class_est(self):
        ze = self.seats.get("二等座")
        return round(ze * 0.75, 1) if ze else None

    def min_seat(self):
        if not self.seats:
            return None
        label, price = min(self.seats.items(), key=lambda kv: kv[1])
        return label, price

    def min_sleeper(self):
        sleepers = [(l, p) for l, p in self.seats.items() if "卧" in l]
        if not sleepers:
            return None
        return min(sleepers, key=lambda kv: kv[1])

    @property
    def duration_minutes(self):
        try:
            h, m = self.duration_text.split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 10 ** 6
