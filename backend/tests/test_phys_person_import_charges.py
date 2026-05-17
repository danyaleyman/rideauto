from __future__ import annotations

from market_pricing_shared import phys_person_import_charges


def test_ice_no_separate_excise_vat():
    c = phys_person_import_charges(
        car_value_rub=2_000_000.0,
        eur_rub=100.0,
        engine_cc=1998,
        age_years=4,
        fuel="ice",
        car_data={"engine_type": "Бензин", "power_hp": 190.0},
    )
    assert c["excise"] == 0.0
    assert c["vat"] == 0.0
    assert c["duty"] > 0.0
    assert c["utilization"] == 1_492_800.0


def test_ev_stp_components():
    c = phys_person_import_charges(
        car_value_rub=3_000_000.0,
        eur_rub=100.0,
        engine_cc=0,
        age_years=1,
        fuel="electric",
        car_data={"power_hp": 200.0},
    )
    assert c["duty"] == 450_000.0
    assert c["excise"] > 0.0
    assert c["vat"] > 0.0
    assert c["customs_total"] == c["customs_fee"] + c["duty"] + c["excise"] + c["utilization"] + c["vat"]
