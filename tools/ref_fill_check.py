#!/usr/bin/env python3
"""Unit-test the nearby-reference gap fill."""
import sys

sys.path.insert(0, ".")
from core.models import FlightDeal  # noqa: E402
from main import _fill_reference_deals  # noqa: E402


def main() -> int:
    deals = [
        FlightDeal(date="2026-09-10", bare_price=300, flight_no="G1"),
        FlightDeal(date="2026-09-14", bare_price=400, flight_no="G2"),
    ]
    out = _fill_reference_deals(deals, "2026-09-09", "2026-09-16", "A", "B")
    by_date = {d.date: d for d in out}
    assert by_date["2026-09-09"].source == "nearby-ref"   # 1d from 09-10
    assert by_date["2026-09-09"].bare_price == 300
    assert by_date["2026-09-12"].source == "nearby-ref"   # nearer to 09-10
    assert by_date["2026-09-12"].bare_price == 300
    assert by_date["2026-09-15"].bare_price == 400
    assert by_date["2026-09-16"].source == "nearby-ref"
    assert len(out) == 8
    # extended radius: within 45d still fills, with ref_offset carrying distance
    far = _fill_reference_deals(deals, "2026-10-01", "2026-10-05", "A", "B")
    assert len(far) == 7  # 5 gap dates + 2 originals
    offsets = {d.date: d.ref_offset for d in far if d.source == "nearby-ref"}
    assert offsets["2026-10-01"] == 17  # nearest priced day is 09-14
    assert offsets["2026-10-05"] == 21
    # truly out of range (>45d): untouched
    out_of_range = _fill_reference_deals(
        deals, "2026-12-01", "2026-12-05", "A", "B")
    assert out_of_range == deals
    print("ref_fill_check OK (near+far refs, ref_offset distances verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
