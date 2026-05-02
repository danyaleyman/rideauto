from __future__ import annotations

from fuel_label_aliases import canonicalize_fuel_label_ru, fuel_alias_resolve, fuel_to_canonical_ru_flat


def test_fuel_json_loads_gasoline_ko():
    flat = fuel_to_canonical_ru_flat()
    assert flat.get("가솔린") == "Бензин"


def test_canonicalize_norm_case_and_ws():
    assert canonicalize_fuel_label_ru("  디젤  ") == "Дизель"
    assert canonicalize_fuel_label_ru("diesel") == "Дизель"


def test_fuel_alias_resolve_typo_in_json():
    assert fuel_alias_resolve("компресированный природный газ") == "Метан"
