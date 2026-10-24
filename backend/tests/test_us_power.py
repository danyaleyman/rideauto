"""Tests for USA power resolution (NHTSA vPIC by VIN + curated us_engine_map)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import us_power
from priceusa import usa_has_customs_inputs


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Тесты не ходят в NHTSA: vPIC выключен, файловый кеш подменён пустым словарём."""
    monkeypatch.setenv("USA_VIN_POWER", "0")
    monkeypatch.setattr(us_power, "_vin_cache", {})


def test_is_usa_source_scope() -> None:
    assert us_power.is_usa_source({"source": "autotrader"})
    assert us_power.is_usa_source({"source": "USA"})
    assert not us_power.is_usa_source({"source": "encar"})
    assert not us_power.is_usa_source({"source": "che168"})
    assert not us_power.is_usa_source({})


def test_us_map_matches_by_normalized_cc() -> None:
    car = {
        "source": "autotrader",
        "mark": "Chevrolet",
        "model": "Equinox",
        "year": 2013,
        "displacement_cc": 2384,
        "engine_type": "Gasoline",
    }
    assert us_power.fill_usa_power(car, allow_vin=False) is True
    assert car["power_hp"] == 182
    assert car["power"] == "182"
    assert car["power_source"] == "us_engine_map"


def test_us_map_respects_fuel_and_year() -> None:
    diesel = {
        "source": "autotrader",
        "mark": "Ram",
        "model": "1500",
        "year": 2018,
        "displacement_cc": 2987,
        "engine_type": "Diesel",
    }
    assert us_power.fill_usa_power(diesel, allow_vin=False) is True
    assert diesel["power_hp"] == 260

    hurricane = {
        "source": "autotrader",
        "mark": "RAM",
        "model": "1500",
        "year": 2025,
        "displacement_cc": 2993,
        "engine_type": "Gasoline",
    }
    assert us_power.fill_usa_power(hurricane, allow_vin=False) is True
    assert hurricane["power_hp"] == 420


def test_us_map_priority_wins_for_same_cc() -> None:
    car = {
        "source": "autotrader",
        "mark": "Cadillac",
        "model": "Escalade",
        "year": 2024,
        "displacement_cc": 6162,
        "engine_type": "Gasoline",
    }
    assert us_power.fill_usa_power(car, allow_vin=False) is True
    assert car["power_hp"] == 682  # Escalade-V (priority 12) перекрывает базовые 420


def test_us_map_keeps_existing_power() -> None:
    car = {"source": "autotrader", "mark": "Ford", "model": "F-150", "year": 2019, "displacement_cc": 3496, "power_hp": 450}
    assert us_power.fill_usa_power(car, allow_vin=False) is False
    assert car["power_hp"] == 450
    assert "power_source" not in car


def test_non_usa_sources_are_untouched() -> None:
    for source in ("encar", "che168"):
        car = {"source": source, "mark": "Ford", "model": "F-150", "year": 2019, "displacement_cc": 3496, "engine_type": "Gasoline"}
        assert us_power.fill_usa_power(car) is False
        assert "power" not in car
        assert "power_hp" not in car


def test_usa_engine_cc_prefers_explicit_cc_over_label() -> None:
    # У Autotrader `displacement` бывает строкой-ярлыком «3.5L»: берём displacement_cc.
    assert us_power.usa_engine_cc({"displacement_cc": 3496, "displacement": "3.5L"}) == 3496
    assert us_power.usa_engine_cc({"engine_volume": 1998, "displacement": "2.0L"}) == 1998
    assert us_power.usa_engine_cc({"displacement": "2.0L"}) == 2000
    assert us_power.usa_engine_cc({}) is None


def test_parse_vpic_row_normalizes_fields() -> None:
    row = {
        "EngineHP": "385.00",
        "EngineHP_to": "395.00",
        "DisplacementCC": "",
        "DisplacementL": "5.7",
        "FuelTypePrimary": "Gasoline",
        "ElectrificationLevel": "",
        "Make": "RAM",
        "Model": "1500",
        "ModelYear": "2019",
    }
    info = us_power._parse_vpic_row(row)
    assert info["hp"] == 395  # для акциза берём максимум из диапазона
    assert info["cc"] == 5700  # DisplacementL → cc
    assert info["electric"] is False
    assert info["make"] == "RAM"


def test_parse_vpic_row_marks_bev() -> None:
    info = us_power._parse_vpic_row(
        {"FuelTypePrimary": "Electric", "ElectrificationLevel": "BEV (Battery Electric Vehicle)"}
    )
    assert info["electric"] is True
    assert info["hp"] is None
    assert info["cc"] is None


def test_lookup_vin_power_rejects_bad_vin() -> None:
    assert us_power.lookup_vin_power("") is None
    assert us_power.lookup_vin_power("SHORTVIN") is None
    assert us_power.lookup_vin_power("1FTFW1E84MFA0000IOQ") is None  # I/O/Q в VIN недопустимы


def test_vin_layer_fills_power_and_displacement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        us_power,
        "lookup_vin_power",
        lambda vin, **kw: {"hp": 400, "cc": 3496, "electric": False},
    )
    car = {
        "source": "autotrader",
        "vin": "1FTFW1E84MFA00000",
        "mark": "Ford",
        "model": "F-150",
        "year": 2021,
        "engine_type": "Gasoline",
    }
    assert us_power.fill_usa_power(car) is True
    assert car["power_hp"] == 400
    assert car["power_source"] == "vin_vpic"
    assert car["displacement_cc"] == 3496
    assert us_power.usa_engine_cc({"displacement_cc": 3496, "displacement": "3.5L"}) == 3496


def test_vin_layer_does_not_override_known_cc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        us_power,
        "lookup_vin_power",
        lambda vin, **kw: {"hp": 400, "cc": 1234, "electric": False},
    )
    car = {"source": "autotrader", "vin": "1FTFW1E84MFA00000", "mark": "Ford", "model": "F-150", "year": 2021, "displacement_cc": 3496}
    assert us_power.fill_usa_power(car) is True
    assert car["displacement_cc"] == 3496


def test_usa_customs_inputs_full_customs_via_map() -> None:
    car = {
        "source": "autotrader",
        "mark": "Ford",
        "model": "F-150",
        "year": 2019,
        "engine_type": "Gasoline",
        "displacement_cc": 3496,
        "price_usd": 30000,
    }
    assert usa_has_customs_inputs(car) is True
    assert int(car["power"]) == 375


def test_us_engine_map_entries_are_wellformed() -> None:
    path = Path(us_power.US_ENGINE_MAP_PATH)
    assert path.is_file(), "data/us_engine_map.json missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    engines = data["engines"]
    assert len(engines) > 100
    for entry in engines:
        assert entry["make"], entry
        assert entry["model_substrings"], entry
        assert 500 <= int(entry["cc"]) <= 9000, entry
        assert 20 <= int(entry["hp"]) <= 2500, entry
        assert entry["fuel"] in ("gas", "diesel", "hybrid", "electric", "lpg"), entry
        for key in ("year_min", "year_max"):
            if key in entry:
                assert 1980 <= int(entry[key]) <= 2035, entry


# --- Библиотека живёт дальше бэкфилла: присвоение на ingest + её рост ---


def test_ingest_enrich_uses_library_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Новая карточка получает power_hp уже на ingest — офлайн, из us_engine_map.json."""
    monkeypatch.delenv("USA_VIN_POWER_AT_INGEST", raising=False)
    monkeypatch.setattr(
        us_power,
        "lookup_vin_power",
        lambda *a, **kw: pytest.fail("vPIC не должен вызываться на ingest по умолчанию"),
    )
    car = {
        "source": "autotrader",
        "vin": "1FTFW1E84MFA00000",
        "mark": "Ford",
        "model": "F-150",
        "year": 2019,
        "displacement_cc": 3496,
        "engine_type": "Gasoline",
    }
    assert us_power.enrich_usa_power_at_ingest(car) is True
    assert car["power_hp"] == 375
    assert car["power_source"] == "us_engine_map"


def test_ingest_vin_layer_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USA_VIN_POWER_AT_INGEST", "1")
    calls: list = []

    def _fake(vin: str, **kw: object) -> dict:
        calls.append(vin)
        return {"hp": 400, "cc": 3496, "electric": False}

    monkeypatch.setattr(us_power, "lookup_vin_power", _fake)
    assert us_power.ingest_vin_lookup_enabled() is True
    car = {"source": "autotrader", "vin": "1FTFW1E84MFA00000", "mark": "Ford", "model": "F-150", "year": 2021}
    assert us_power.enrich_usa_power_at_ingest(car) is True
    assert calls == ["1FTFW1E84MFA00000"]
    assert car["power_source"] == "vin_vpic"


def test_ingest_enrich_ignores_korea_and_china(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USA_VIN_POWER_AT_INGEST", "1")
    monkeypatch.setattr(us_power, "lookup_vin_power", lambda *a, **kw: pytest.fail("не для чужих рынков"))
    car = {"source": "encar", "mark": "Kia", "model": "Rio", "year": 2021, "displacement": "1400"}
    assert us_power.enrich_usa_power_at_ingest(car) is False
    assert "power" not in car and "power_hp" not in car


def test_library_growth_covers_new_models(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Дописали запись в библиотеку → новые карточки этой модели резолвятся без кода и сети."""
    lib = tmp_path / "us_engine_map.json"
    lib.write_text(
        json.dumps(
            {
                "engines": [
                    {
                        "make": "Toyota",
                        "model_substrings": ["tacoma"],
                        "cc": 3500,
                        "fuel": "gas",
                        "hp": 278,
                        "year_min": 2016,
                        "year_max": 2024,
                        "priority": 9,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(us_power, "US_ENGINE_MAP_PATH", lib)
    us_power.invalidate_us_engine_map_cache()
    try:
        car = {
            "source": "autotrader",
            "mark": "Toyota",
            "model": "Tacoma",
            "year": 2022,
            "displacement_cc": 3456,
            "engine_type": "Gasoline",
        }
        assert us_power.enrich_usa_power_at_ingest(car) is True
        assert car["power_hp"] == 278
        assert car["power_source"] == "us_engine_map"
    finally:
        us_power.invalidate_us_engine_map_cache()


def test_parser_assigns_power_at_ingest(monkeypatch: pytest.MonkeyPatch) -> None:
    """normalize_listing (путь ingest Autotrader) отдаёт карточку уже с power_hp из библиотеки."""
    from scraper_pipeline.autotrader.parser import normalize_listing

    monkeypatch.delenv("USA_VIN_POWER_AT_INGEST", raising=False)
    monkeypatch.setattr(
        us_power,
        "lookup_vin_power",
        lambda *a, **kw: pytest.fail("vPIC не должен вызываться на ingest"),
    )
    listing = {
        "id": 123456789,
        "make": {"name": "Ford", "code": "FORD"},
        "model": {"name": "F-150", "code": "F150"},
        "year": 2019,
        "displacementUOM": 3.5,
        "vin": "1FTFW1E84MFA00000",
        "fuelType": {"name": "Gasoline"},
        "mileage": {"value": 41000},
        "pricingDetail": {"salePrice": 31000},
    }
    car = normalize_listing(listing, listing_id="123456789", depth="vdp")
    assert car["source"] == "autotrader"
    assert car["displacement_cc"] == 3500
    assert car["power_hp"] == 375
    assert car["power"] == "375"
    assert car["power_source"] == "us_engine_map"


def test_vin_cache_without_hp_is_requeried_after_ttl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("USA_VIN_POWER", "1")
    monkeypatch.setattr(us_power, "VIN_CACHE_PATH", tmp_path / "vin_power_cache.json")
    vin = "1FTFW1E84MFA00000"
    stale_ts = int(time.time()) - us_power._VIN_CACHE_NOHP_TTL_SEC - 60
    monkeypatch.setattr(us_power, "_vin_cache", {vin: {"hp": None, "cc": None, "ts": stale_ts}})
    calls: list = []

    def _row(v: str) -> dict:
        calls.append(v)
        return {
            "EngineHP": "400",
            "DisplacementCC": "3496",
            "ModelYear": "2021",
            "Make": "Ford",
            "Model": "F-150",
            "FuelTypePrimary": "Gasoline",
        }

    monkeypatch.setattr(us_power, "_vpic_query", _row)
    info = us_power.lookup_vin_power(vin)
    assert calls == [vin]
    assert info is not None and info["hp"] == 400


def test_vin_cache_without_hp_within_ttl_is_not_requeried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USA_VIN_POWER", "1")
    vin = "1FTFW1E84MFA00000"
    monkeypatch.setattr(us_power, "_vin_cache", {vin: {"hp": None, "cc": None, "ts": int(time.time()) - 3600}})
    monkeypatch.setattr(us_power, "_vpic_query", lambda v: pytest.fail("свежий пустой ответ не перезапрашиваем"))
    assert us_power.lookup_vin_power(vin) is None


def test_suggest_library_entries_groups_and_medians() -> None:
    samples = [
        {"make": "Ford", "model": "Bronco", "cc": 2694, "fuel": "Gasoline", "year": 2021, "hp": 300},
        {"make": "Ford", "model": "Bronco", "cc": 2694, "fuel": "Gasoline", "year": 2024, "hp": 330},
        {"make": "Ford", "model": "Bronco", "cc": 2694, "fuel": "Gasoline", "year": 2022, "hp": 315},
        {"make": "Ford", "model": "Bronco", "cc": None, "fuel": "Gasoline", "hp": 999},
        {"make": "", "model": "Bronco", "cc": 2694, "fuel": "Gasoline", "hp": 300},
    ]
    entries = us_power.suggest_library_entries(samples)
    assert len(entries) == 1
    e = entries[0]
    assert e["make"] == "Ford"
    assert e["model_substrings"] == ["bronco"]
    assert e["cc"] == 2700  # объём нормализован к номиналу
    assert e["fuel"] == "gas"
    assert e["hp"] == 315  # медиана наблюдений
    assert e["samples"] == 3
    assert e["year_min"] == 2021 and e["year_max"] == 2024
    assert e["priority"] == 5
    assert us_power.suggest_library_entries(samples, min_count=4) == []


def test_suggest_library_entries_skips_cc_less_and_omits_years() -> None:
    entries = us_power.suggest_library_entries(
        [
            {"make": "Tesla", "model": "Model 3", "cc": None, "fuel": "Electric", "year": 2022, "hp": 346},
            {"make": "Toyota", "model": "Tacoma", "cc": 3456, "fuel": "Gasoline", "hp": 278},
        ]
    )
    assert [e["model_substrings"][0] for e in entries] == ["tacoma"]
    # нет модельных годов → ключей нет, иначе упал бы тест wellformed по файлу
    assert "year_min" not in entries[0] and "year_max" not in entries[0]
    assert entries[0]["cc"] == 3500

