# -*- coding: utf-8 -*-
"""v0.33 stop/transfer transparency tests.

Board entries already carry layover data (connecting first legs land at
the transfer city with a real arr) and via data (through flights store
the stop city + nextschtime stop arrival). The enricher must surface
both as deal stop_* fields for the UI timeline.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as app_main  # noqa: E402
from core.models import FlightDeal  # noqa: E402


class TestStopInfo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = app_main.DATA_DIR
        app_main.DATA_DIR = self._tmp.name

    def tearDown(self):
        app_main.DATA_DIR = self._orig
        self._tmp.cleanup()

    def _db_write(self, flights):
        with open(os.path.join(self._tmp.name, "flight_sched_db.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"updated": 1, "flights": flights}, f,
                      ensure_ascii=False)

    def _run(self, deal):
        route = {"from_city": "杭州", "to_city": "成都",
                 "from_iata": "HGH", "to_iata": "CTU"}
        out = app_main._enrich_flight_times(
            None, {}, route, [deal], {}, {}, False,
            "2026-09-11", "2026-09-11")
        return out[0]

    def test_connecting_first_leg_transfer_info(self):
        # 2026-09-11 is a Friday (dow=4); first leg HGH->Wuhan is on the
        # board with a real dual-time row
        self._db_write({"MU6567": {"dows": {"4": {
            "dep": "07:10", "arr": "08:55", "from": "杭州", "to": "武汉",
            "via": "", "via_arr": "", "src": "airport-board"}}}})
        d = self._run(FlightDeal(date="2026-09-11", bare_price=400,
                                 flight_no="MU6567/MU2657"))
        self.assertEqual(d.dep_time, "07:10")
        self.assertEqual(d.stop_kind, "transfer")
        self.assertEqual(d.stop_city, "武汉")
        self.assertEqual(d.stop_arr, "08:55")

    def test_via_stop_info_surfaced(self):
        self._db_write({"GJ8885": {"dows": {"4": {
            "dep": "09:35", "arr": "", "from": "杭州", "to": "成都",
            "via": "襄阳", "via_arr": "11:35", "src": "airport-board"}}}})
        d = self._run(FlightDeal(date="2026-09-11", bare_price=400,
                                 flight_no="GJ8885"))
        self.assertEqual(d.dep_time, "09:35")
        self.assertEqual(d.stop_kind, "via")
        self.assertEqual(d.stop_city, "襄阳")
        self.assertEqual(d.stop_arr, "11:35")

    def test_hopoff_via_suppressed(self):
        # destination IS the via city (HGH->TWC via CTU sold as HGH->CTU):
        # a "stops at your destination" hint would contradict the ticket
        self._db_write({"GJ8281": {"dows": {"4": {
            "dep": "08:05", "arr": "", "from": "杭州", "to": "图木舒克",
            "via": "成都", "via_arr": "11:30", "src": "airport-board"}}}})
        d = self._run(FlightDeal(date="2026-09-11", bare_price=400,
                                 flight_no="GJ8281"))
        self.assertEqual(d.dep_time, "08:05")
        self.assertEqual(d.stop_kind, "")
        self.assertEqual(d.stop_city, "")

    def test_amadeus_dep_not_overwritten_by_board(self):
        # amadeus already gave the first-leg dep: the board may supply
        # transfer info but must not overwrite dep or downgrade time_src
        self._db_write({"MU6567": {"dows": {"4": {
            "dep": "07:10", "arr": "08:55", "from": "杭州", "to": "武汉",
            "via": "", "via_arr": "", "src": "airport-board"}}}})
        d = FlightDeal(date="2026-09-11", bare_price=400,
                       flight_no="MU6567/MU2657")
        d.dep_time = "07:30"
        d.time_src = "amadeus"
        d.dep_src = "amadeus"
        d = self._run(d)
        self.assertEqual(d.dep_time, "07:30")
        self.assertEqual(d.time_src, "amadeus")
        self.assertEqual(d.stop_kind, "transfer")
        self.assertEqual(d.stop_city, "武汉")
        self.assertEqual(d.stop_arr, "08:55")


if __name__ == "__main__":
    unittest.main()
