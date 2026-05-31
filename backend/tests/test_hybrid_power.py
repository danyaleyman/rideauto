from __future__ import annotations

from hybrid_power import enrich_hybrid_power_fields, resolve_hybrid_components
from market_pricing_shared import ice_engine_inputs, parse_power_hp, phys_person_import_charges, utilization_phys_person_rub


def _ioniq_hybrid_car() -> dict:
    return {
        "mark": "Hyundai",
        "model": "The New Ioniq Hybrid",
        "generation": "1.6 HEV",
        "engine_type": "가솔린+전기",
        "displacement": "1580",
        "power": "105",
        "power_source": "hp_catalog_llm",
        "year": "2019",
    }


def test_enrich_ioniq_sets_system_and_motor_hp():
    car = _ioniq_hybrid_car()
    assert enrich_hybrid_power_fields(car) is True
    assert car["power_ice_hp"] == 105
    assert car["power_electric_hp"] == 44  # rounded 43.5
    assert car["hybrid_layout"] == "parallel"
    assert car["power"] == "149"  # 105 + 43.5
    assert car["power_hp"] == 149


def test_parse_power_hp_hybrid_returns_system():
    car = _ioniq_hybrid_car()
    enrich_hybrid_power_fields(car)
    assert parse_power_hp(car) == 149.0


def test_ice_engine_inputs_keeps_ice_for_customs():
    car = _ioniq_hybrid_car()
    enrich_hybrid_power_fields(car)
    cc, hp_ice = ice_engine_inputs(car, "hybrid")
    assert cc == 1580
    assert hp_ice == 105.0


def test_utilization_hybrid_parallel_full_sum():
    car = {
        "engine_type": "가솔린+전기",
        "mark": "Hyundai",
        "model": "Sonata Hybrid",
        "displacement": "2000",
        "power": "152",
    }
    enrich_hybrid_power_fields(car)
    u_ice_only = utilization_phys_person_rub(
        engine_cc=2000,
        age_years=2,
        power_hp_ice=152.0,
        fuel="hybrid",
        car_data={"engine_type": "가솔린+전기"},
    )
    u_full = utilization_phys_person_rub(
        engine_cc=2000,
        age_years=2,
        power_hp_ice=152.0,
        fuel="hybrid",
        car_data=car,
    )
    assert u_ice_only == 3400.0  # 152 л.с. — ещё льгота
    assert u_full > 100_000.0  # 152+51=203 л.с. сумма


def test_utilization_hybrid_strong_ed_raises_util_vs_ice_only():
    car = {
        "engine_type": "가솔린+전기",
        "power": "150",
        "power_ice_hp": 150,
        "power_electric_hp": 200,
        "mark": "TestMake",
        "model": "Test Hybrid",
        "displacement": "2500",
    }
    u_ice_only = utilization_phys_person_rub(
        engine_cc=2500,
        age_years=2,
        power_hp_ice=150.0,
        fuel="hybrid",
        car_data={"engine_type": "가솔린+전기"},
    )
    u_full = utilization_phys_person_rub(
        engine_cc=2500,
        age_years=2,
        power_hp_ice=150.0,
        fuel="hybrid",
        car_data=car,
    )
    assert u_ice_only == 3400.0  # 0–3 лет, только ДВС 150 л.с.
    assert u_full > 100_000.0  # с учётом ЭД: effective 240 л.с. >> 160


def test_phys_person_import_uses_enriched_hybrid_car_data():
    car = _ioniq_hybrid_car()
    enrich_hybrid_power_fields(car)
    charges = phys_person_import_charges(
        car_value_rub=1_000_000.0,
        eur_rub=100.0,
        engine_cc=1580,
        age_years=7,
        fuel="hybrid",
        car_data=car,
    )
    assert charges["utilization"] == 5200.0  # 149 л.с. сумма, 7 лет — льгота


def test_series_hybrid_uses_ed_only_for_display():
    car = {
        "mark": "Nissan",
        "model": "Note e-POWER",
        "engine_type": "가솔린+전기",
        "power": "79",
        "power_ice_hp": 79,
        "power_electric_hp": 136,
        "hybrid_layout": "series",
        "displacement": "1200",
    }
    enrich_hybrid_power_fields(car)
    assert car["power_hp"] == 136


def test_infer_hybrid_layout_defaults_parallel_for_hev():
    from hybrid_power import infer_hybrid_layout

    assert infer_hybrid_layout(_ioniq_hybrid_car()) == "parallel"
    assert infer_hybrid_layout({"model": "Outlander PHEV", "engine_type": "hybrid"}) == "parallel"
    assert infer_hybrid_layout({"model": "Note e-POWER", "engine_type": "hybrid"}) == "series"


def test_classify_fuel_russian_gasoline_electric():
    from market_pricing_shared import classify_fuel
    from hybrid_power import is_hybrid_listing

    assert classify_fuel({"engine_type": "Бензин + электричество"}) == "hybrid"
    assert is_hybrid_listing({"engine_type": "Бензин + электричество"}) is True
    assert is_hybrid_listing({"engine_type": "Дизель + электричество"}) is True


def test_unknown_hybrid_gets_estimated_ed():
    from hybrid_power import enrich_hybrid_power_fields

    car = {
        "mark": "Toyota",
        "model": "Mystery Hybrid Van",
        "engine_type": "Бензин + электричество",
        "displacement": "2000",
        "power": "140",
    }
    assert enrich_hybrid_power_fields(car) is True
    assert int(car["power"]) > 140
    assert car.get("power_electric_hp")
    assert car.get("power_source") == "hybrid_power_estimate"


def test_hybrid_without_encar_power():
    from hybrid_power import enrich_hybrid_power_fields

    carnival = {
        "mark": "Kia",
        "model": "The New Carnival 4th Gen",
        "generation": "HEV 7-Seater Hi-Limousine",
        "engine_type": "Бензин + электричество",
        "displacement": "1600",
        "power": "",
    }
    assert enrich_hybrid_power_fields(carnival) is True
    assert carnival["power_hp"] == 245
    assert carnival["power_ice_hp"] == 180
    assert carnival["power_electric_hp"] == 65

    philant = {
        "mark": "Renault Korea (Samsung)",
        "model": "Philant",
        "generation": "1.5 E-TECH Esprit Alpine 2WD",
        "engine_type": "Бензин + электричество",
        "displacement": "1499",
        "power": "",
    }
    assert enrich_hybrid_power_fields(philant) is True
    assert philant["power_hp"] == 160
    assert philant["power_ice_hp"] == 103
    assert philant["power_electric_hp"] == 57


def test_resolve_components_factory_lookup():
    comp = resolve_hybrid_components(_ioniq_hybrid_car())
    assert comp is not None
    assert comp["ice_hp"] == 105.0
    assert comp["electric_hp"] == 43.5
    assert comp["system_hp"] == 141.0
