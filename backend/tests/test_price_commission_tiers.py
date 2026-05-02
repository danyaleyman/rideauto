from __future__ import annotations

from market_pricing_shared import (
    COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB,
    commission_rub_tiered,
    parse_commission_schedule_from_config,
)


def test_commission_tiers_korea_exact_boundaries():
    sched = list(COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB)
    assert commission_rub_tiered(1_500_000, 1.0, 1.0, sched)[0] == 150_000
    assert commission_rub_tiered(1_500_000.01, 0, 0, sched)[0] == 230_000
    assert commission_rub_tiered(3_000_000, 0, 0, sched)[0] == 230_000
    assert commission_rub_tiered(3_000_000.01, 0, 0, sched)[0] == 300_000
    assert commission_rub_tiered(7_000_000, 0, 0, sched)[0] == 300_000
    assert commission_rub_tiered(7_000_000.01, 0, 0, sched)[0] == 400_000


def test_parse_commission_car_tiers_from_config_json_shape():
    raw = [[1500000, 111], [None, 999]]
    s = parse_commission_schedule_from_config(raw)
    assert s[-1] == (float("inf"), 999.0)
    assert s[0][1] == 111.0
