from fastapi_app.facet_normalize import expand_filter_values


def test_expand_color_includes_ko_tokens_for_canonical_ru():
    flat = {"region": "korea"}
    out = expand_filter_values("color", ["Черный"], query_flat=flat)
    assert "Черный" in out
    assert "검정색" in out


def test_expand_color_keeps_clicked_raw():
    # Регрессия: выбранное сырое значение всегда попадает в OR-фильтр Meili
    flat = {"region": "korea"}
    out = expand_filter_values("color", ["검정색"], query_flat=flat)
    assert "검정색" in out
    assert any(x in ("Черный", "검정색") for x in out)


def test_expand_fuel_includes_original_and_canon():
    flat = {"region": "korea"}
    out = expand_filter_values("fuel", ["가솔린"], query_flat=flat)
    assert "가솔린" in out

