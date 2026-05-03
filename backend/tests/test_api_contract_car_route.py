"""Контракт GET /api/car/{ref} без поднятия полного приложения (мок БД + кэш)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fastapi_app.config import get_settings
from fastapi_app.routers import car as car_router
from fastapi_app.schemas.catalog_contract import validate_car_detail_envelope_v1

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "api_contract"


class _EmptyQueryParams:
    def multi_items(self) -> list[tuple[str, str]]:
        return []


def _request_with_pool(pool: object) -> SimpleNamespace:
    state = SimpleNamespace(pg_pool=pool)
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app, query_params=_EmptyQueryParams())


@pytest.mark.asyncio
async def test_get_car_envelope_matches_golden_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRA_LEGACY_FALLBACKS_ENABLED", "1")
    monkeypatch.delenv("WRA_CLEAN_READ_MODE", raising=False)
    monkeypatch.setenv("WRA_CLEAN_READ_PERCENT", "0")
    monkeypatch.setenv("WRA_API_CONTRACT_VERSION", "v1")
    get_settings.cache_clear()

    golden_path = _FIXTURES / "v1" / "car_detail_encar.json"
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    row = {k: v for k, v in expected["result"].items() if k not in ("read_model", "read_model_version")}

    async def fake_fetch(_pool: object, ref: str) -> dict | None:
        assert ref == "snap-encar-1"
        return row

    async def passthrough_cached(
        _request: object,
        *,
        segment: str,
        ttl_sec: int,
        flat: object,
        compute,
    ) -> dict:
        return await compute()

    monkeypatch.setattr(car_router, "fetch_car_any_id", fake_fetch)
    monkeypatch.setattr(car_router, "serve_cached_json", passthrough_cached)

    req = _request_with_pool(object())
    out = await car_router.get_car("snap-encar-1", req)
    validate_car_detail_envelope_v1(out)

    def _norm(obj: object) -> object:
        if isinstance(obj, float):
            return round(obj, 6)
        if isinstance(obj, dict):
            return {k: _norm(v) for k, v in sorted(obj.items())}
        if isinstance(obj, list):
            return [_norm(x) for x in obj]
        return obj

    assert _norm(out) == _norm(expected)
