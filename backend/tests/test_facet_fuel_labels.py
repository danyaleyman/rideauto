from fastapi_app.facet_normalize import _canon_ru_fuel


def test_facet_fuel_korean_aliases_match_frontend_labels():
    assert _canon_ru_fuel("가솔린") == "Бензин"
    assert _canon_ru_fuel("디젤") == "Дизель"
    assert _canon_ru_fuel("가솔린 + 전기") == "Гибрид (Бензин)"
    assert _canon_ru_fuel("LPG+전기") == "Электро (+ГБО)"
    assert _canon_ru_fuel("LPG(일반인 구입)") == "Газ"


def test_facet_fuel_legacy_ru_static_strings():
    assert _canon_ru_fuel("Бензин + электричество") == "Гибрид (Бензин)"
    assert _canon_ru_fuel("Электричество") == "Электро"

