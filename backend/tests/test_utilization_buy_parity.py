"""Паритет утилизационного сбора с web/src/components/buy/BuyCalculator.tsx (UTIL_SELF_CHECK_CASES)."""

from __future__ import annotations

import pytest

from market_pricing_shared import utilization_buy_page_rub, utilization_phys_person_rub


@pytest.mark.parametrize(
    "name,age,eng,hybrid,vol,hp_i,hp_e,purpose,expected",
    [
        ("ICE personal loyal 0-3 <=160hp", "0-3", "petrol", "none", 1598, 150, 0, "personal", 3400),
        ("ICE personal loyal 3-5 <=160hp", "3-5", "petrol", "none", 1598, 150, 0, "personal", 5200),
        ("ICE legal no-loyal 0-3 <=160hp", "0-3", "petrol", "none", 1598, 150, 0, "legal", 72400),
        ("ICE 0-3 1-2L 180hp", "0-3", "petrol", "none", 1998, 180, 0, "personal", 900000),
        ("ICE 3-5 1-2L 180hp", "3-5", "petrol", "none", 1998, 180, 0, "personal", 1492800),
        ("ICE 5+ 1-2L 180hp", "5+", "petrol", "none", 1998, 180, 0, "personal", 1492800),
        ("Boundary DVS exactly 160hp stays loyal", "0-3", "petrol", "none", 1998, 160, 0, "personal", 3400),
        ("Diesel 0-3 2-3L >160hp", "0-3", "diesel", "none", 2498, 190, 0, "personal", 2402400),
        ("Petrol 0-3 2-3L >160hp", "0-3", "petrol", "none", 2498, 190, 0, "personal", 2364000),
    ],
)
def test_utilization_buy_page_matches_calculator(
    name: str,
    age: str,
    eng: str,
    hybrid: str,
    vol: int,
    hp_i: float,
    hp_e: float,
    purpose: str,
    expected: int,
) -> None:
    _ = name
    got = utilization_buy_page_rub(
        age=age,
        eng_type=eng,
        hybrid_type=hybrid,
        vol=vol,
        hp_ice=hp_i,
        hp_ed=hp_e,
        purpose=purpose,
    )
    assert got == float(expected)


def test_utilization_phys_person_encar_ice_maps_to_buy_page():
    """Каталог Encar: тот же результат, что у блока getUtil для бензина."""
    car = {"engine_type": "Бензин", "mark": "Hyundai"}
    u = utilization_phys_person_rub(
        engine_cc=1598,
        age_years=4,
        power_hp_ice=180.0,
        fuel="ice",
        car_data=car,
    )
    assert u == 1_492_800.0
