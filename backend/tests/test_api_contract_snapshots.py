"""Golden JSON for public API contract (WRA_API_CONTRACT_VERSION)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from fastapi_app.catalog_slim import slim_catalog_car
from fastapi_app.config import get_settings
from fastapi_app.schemas.api import CarDetailResponse
from fastapi_app.schemas.catalog_contract import (
    SUPPORTED_API_CONTRACT_FIXTURE_VERSIONS,
    validate_car_detail_envelope_v1,
    validate_catalog_search_response_v1,
    validate_slim_catalog_item_v1,
)
from read_models import build_car_detail_read_model

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "api_contract"


def _norm_json(obj: object) -> object:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: _norm_json(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_norm_json(x) for x in obj]
    return obj


def _fixture_car_and_row() -> tuple[dict, dict]:
    """Deterministic Encar-like row; ASCII-only strings for stable golden files."""
    car = {
        "data": {
            "source": "encar",
            "mark_en": "Kia",
            "model_en": "K5",
            "generation_en": "1.6 Turbo",
            "mark": "Kia",
            "model": "K5",
            "generation": "1.6 Turbo",
            "year": "202108.0",
            "engine_type": "gasoline",
            "transmission_type": "automatic",
            "drive_type": "",
            "body_type": "sedan",
            "color": "white",
            "km_age": "10000.0",
            "power": "180",
            "my_price": 3500000.0,
            "inner_id": "inner-snap-1",
            "images": ["https://ci.encar.com/c1.jpg"],
            "pricing_clean": {"final_price_rub": 4200000.0, "pricing_tier": "full_customs"},
        },
        "inner_id": "inner-snap-1",
        "_catalog_updated_at": "2026-01-15T12:00:05+00:00",
    }
    row = {
        "id": "snap-encar-1",
        "data": car["data"],
        "_catalog_created_at": "2026-01-15T12:00:00+00:00",
        "_catalog_updated_at": "2026-01-15T12:00:05+00:00",
    }
    return car, row


@pytest.fixture(autouse=True)
def _api_contract_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    monkeypatch.delenv("WRA_CLEAN_READ_MODE", raising=False)
    monkeypatch.setenv("WRA_CLEAN_READ_PERCENT", "0")
    monkeypatch.setenv("WRA_API_CONTRACT_VERSION", "v1")
    get_settings.cache_clear()


def test_slim_item_matches_golden_v1() -> None:
    car, _ = _fixture_car_and_row()
    got = slim_catalog_car(car, "snap-encar-1")
    path = _FIXTURES / "v1" / "slim_item_encar.json"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert _norm_json(got) == _norm_json(expected)


def test_car_detail_matches_golden_v1() -> None:
    _, row = _fixture_car_and_row()
    rm = build_car_detail_read_model(row, use_clean=False, api_version="v1")
    got = CarDetailResponse(result=rm, api_version="v1").model_dump()
    path = _FIXTURES / "v1" / "car_detail_encar.json"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert _norm_json(got) == _norm_json(expected)


def test_slim_item_matches_golden_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRA_API_CONTRACT_VERSION", "v2")
    get_settings.cache_clear()
    car, _ = _fixture_car_and_row()
    got = slim_catalog_car(car, "snap-encar-1")
    path = _FIXTURES / "v2" / "slim_item_encar.json"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert _norm_json(got) == _norm_json(expected)


def test_car_detail_matches_golden_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRA_API_CONTRACT_VERSION", "v2")
    get_settings.cache_clear()
    _, row = _fixture_car_and_row()
    rm = build_car_detail_read_model(row, use_clean=False, api_version="v2")
    got = CarDetailResponse(result=rm, api_version="v2").model_dump()
    path = _FIXTURES / "v2" / "car_detail_encar.json"
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert _norm_json(got) == _norm_json(expected)


def test_car_detail_clean_read_matches_golden_v2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRA_API_CONTRACT_VERSION", "v2")
    get_settings.cache_clear()
    path = _FIXTURES / "v2" / "car_detail_encar_clean.json"
    full = json.loads(path.read_text(encoding="utf-8"))
    row = {k: v for k, v in full["result"].items() if k not in ("read_model", "read_model_version")}
    rm = build_car_detail_read_model(row, use_clean=True, api_version="v2")
    got = CarDetailResponse(result=rm, api_version="v2").model_dump()
    assert _norm_json(got) == _norm_json(full)


def test_car_detail_clean_read_matches_golden_v1() -> None:
    """use_clean=True: read_model берёт identity/spec из *_clean (корейские строки в golden)."""
    path = _FIXTURES / "v1" / "car_detail_encar_clean.json"
    full = json.loads(path.read_text(encoding="utf-8"))
    row = {k: v for k, v in full["result"].items() if k not in ("read_model", "read_model_version")}
    rm = build_car_detail_read_model(row, use_clean=True, api_version="v1")
    got = CarDetailResponse(result=rm, api_version="v1").model_dump()
    assert _norm_json(got) == _norm_json(full)


def test_search_meta_includes_api_version() -> None:
    from fastapi_app.schemas.api import SearchMeta

    m = SearchMeta(
        total=1,
        limit=12,
        per_page=12,
        pages=1,
        offset=0,
        api_version="v1",
    )
    d = m.model_dump()
    assert d.get("api_version") == "v1"


def test_api_contract_fixture_dirs_complete() -> None:
    """CI: при добавлении v2 положите golden в tests/fixtures/api_contract/v2/ и расширьте кортеж."""
    for ver in SUPPORTED_API_CONTRACT_FIXTURE_VERSIONS:
        base = _FIXTURES / ver
        assert (base / "slim_item_encar.json").is_file(), ver
        assert (base / "car_detail_encar.json").is_file(), ver
        assert (base / "car_detail_encar_clean.json").is_file(), ver


def test_golden_files_validate_pydantic_models() -> None:
    slim = json.loads((_FIXTURES / "v1" / "slim_item_encar.json").read_text(encoding="utf-8"))
    validate_slim_catalog_item_v1(slim)
    for name in ("car_detail_encar.json", "car_detail_encar_clean.json"):
        body = json.loads((_FIXTURES / "v1" / name).read_text(encoding="utf-8"))
        validate_car_detail_envelope_v1(body)


def test_v2_golden_files_validate_strict() -> None:
    slim = json.loads((_FIXTURES / "v2" / "slim_item_encar.json").read_text(encoding="utf-8"))
    validate_slim_catalog_item_v1(slim, require_catalog_updated_at=True)
    for name in ("car_detail_encar.json", "car_detail_encar_clean.json"):
        body = json.loads((_FIXTURES / "v2" / name).read_text(encoding="utf-8"))
        validate_car_detail_envelope_v1(body)


def test_validate_search_response_full_mode_accepts_raw_rows() -> None:
    raw = {"id": "x", "data": {"mark": "Kia"}}
    body = {
        "meta": {
            "total": 1,
            "limit": 12,
            "per_page": 12,
            "pages": 1,
            "offset": 0,
            "list_mode": "full",
            "api_version": "v1",
        },
        "result": [raw],
    }
    validate_catalog_search_response_v1(body)


def test_validate_search_v2_rejects_slim_without_catalog_updated_at() -> None:
    slim = json.loads((_FIXTURES / "v1" / "slim_item_encar.json").read_text(encoding="utf-8"))
    slim.pop("catalog_updated_at", None)
    body = {
        "meta": {
            "total": 1,
            "limit": 12,
            "per_page": 12,
            "pages": 1,
            "offset": 0,
            "list_mode": "slim",
            "api_version": "v2",
        },
        "result": [slim],
    }
    with pytest.raises(ValueError, match="catalog_updated_at"):
        validate_catalog_search_response_v1(body)


def test_validate_search_slim_response_with_golden_item() -> None:
    slim = json.loads((_FIXTURES / "v1" / "slim_item_encar.json").read_text(encoding="utf-8"))
    body = {
        "meta": {
            "total": 1,
            "limit": 12,
            "per_page": 12,
            "pages": 1,
            "offset": 0,
            "list_mode": "slim",
            "sort": "date_new",
            "api_version": "v1",
        },
        "result": [slim],
    }
    validate_catalog_search_response_v1(body)


def test_slim_v2_fails_without_catalog_updated_at(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRA_API_CONTRACT_VERSION", "v2")
    get_settings.cache_clear()
    car, _ = _fixture_car_and_row()
    del car["_catalog_updated_at"]
    with pytest.raises(ValueError, match="catalog_updated_at"):
        slim_catalog_car(car, "snap-encar-1")


def test_slim_unchanged_when_clean_read_on_and_only_en_identity_in_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """clean-read не меняет slim, если в data только EN *_en (как в основном golden)."""
    monkeypatch.setenv("WRA_CLEAN_READ_MODE", "1")
    monkeypatch.setenv("WRA_CLEAN_READ_PERCENT", "100")
    get_settings.cache_clear()
    car, _ = _fixture_car_and_row()
    got = slim_catalog_car(car, "snap-encar-1")
    expected = json.loads((_FIXTURES / "v1" / "slim_item_encar.json").read_text(encoding="utf-8"))
    assert _norm_json(got) == _norm_json(expected)
    validate_slim_catalog_item_v1(got)
