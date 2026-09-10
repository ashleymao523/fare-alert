# -*- coding: utf-8 -*-
"""M5 适配器一致性测试: 任何新源过夹具即可接入(DoD)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.adapters import (AmadeusIntlAdapter, FetchQuery, QunarCalendarAdapter,
                           REGISTRY, ReplayAdapter, fixture_dir, register,
                           validate_deals)
from core.models import FlightDeal


def _load(name):
    return ReplayAdapter(os.path.join(fixture_dir(), name))


class AdapterConformanceTest(unittest.TestCase):

    def test_registry_has_wrapped_sources(self):
        for aid in ("qunar-calendar", "qunar-intl", "amadeus-intl"):
            self.assertIn(aid, REGISTRY)
        self.assertLess(REGISTRY["qunar-calendar"].priority,
                        REGISTRY["qunar-intl"].priority)

    def test_replay_fixture_passes_conformance(self):
        a = _load("replay-sample.json")
        q = FetchQuery("杭州", "重庆", "2026-09-15", "2026-09-17")
        deals = a.fetch(None, {}, {}, q)
        self.assertEqual(len(deals), 3)
        self.assertEqual(validate_deals(deals, a.id, q.date_from, q.date_to), [])

    def test_replay_intl_keeps_times_and_sorts(self):
        a = _load("replay-intl.json")
        q = FetchQuery("杭州", "曼谷", "2026-09-20", "2026-09-21")
        deals = a.fetch(None, {}, {}, q)
        self.assertEqual(deals[0].dep_time, "18:05")
        self.assertEqual(deals[0].arr_time, "22:30")
        self.assertLessEqual(deals[0].bare_price, deals[1].bare_price)
        self.assertEqual(validate_deals(deals, a.id, q.date_from, q.date_to), [])

    def test_replay_empty_is_valid(self):
        a = _load("replay-empty.json")
        q = FetchQuery("杭州", "重庆", "2026-09-15", "2026-09-17")
        self.assertEqual(a.fetch(None, {}, {}, q), [])
        self.assertEqual(validate_deals([], a.id, q.date_from, q.date_to), [])

    def test_replay_filters_out_of_range(self):
        a = _load("replay-sample.json")
        q = FetchQuery("杭州", "重庆", "2026-09-16", "2026-09-16")
        deals = a.fetch(None, {}, {}, q)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0].date, "2026-09-16")

    def test_validate_deals_catches_bad_source_and_price(self):
        bad = [FlightDeal(date="2026-09-15", bare_price=-1,
                          flight_no="X1", source="other")]
        errs = validate_deals(bad, "replay-sample", "2026-09-15", "2026-09-17")
        self.assertTrue(any("价格" in e for e in errs))
        self.assertTrue(any("source" in e for e in errs))

    def test_amadeus_requires_keys(self):
        ok, hint = AmadeusIntlAdapter().is_configured({})
        self.assertFalse(ok)
        self.assertIn("Amadeus", hint)
        ok2, _ = AmadeusIntlAdapter().is_configured(
            {"amadeus": {"api_key": "k", "api_secret": "s"}})
        self.assertTrue(ok2)

    def test_register_overrides_for_tests(self):
        class _Tmp(QunarCalendarAdapter):
            id = "qunar-calendar"
        register(_Tmp)
        self.assertIs(REGISTRY["qunar-calendar"], _Tmp)


if __name__ == "__main__":
    unittest.main()
