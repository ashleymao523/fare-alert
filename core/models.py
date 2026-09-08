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
    second_class: float | None = None

    @property
    def duration_minutes(self):
        try:
            h, m = self.duration_text.split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 10**6

    @property
    def student_second_class_est(self):
        """动车组学生票=二等座公布票价x75%.此处用当前执行价估算,为偏低参考值,以12306下单页为准."""
        if self.second_class:
            return round(self.second_class * 0.75, 1)
        return None
