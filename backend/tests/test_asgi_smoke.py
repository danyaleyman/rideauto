"""Минимальный E2E: lifespan + HTTP без реального Postgres (пул замокан)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def mock_asyncpg_pool(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    pool = MagicMock()
    pool.close = AsyncMock()
    created: dict[str, bool] = {"ok": False}

    async def _create_pool(*_a, **_kw):
        created["ok"] = True
        return pool

    monkeypatch.setattr("fastapi_app.main.asyncpg.create_pool", _create_pool)
    return pool


def test_api_health_with_lifespan(mock_asyncpg_pool: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRA_REDIS_URL", "")
    from fastapi_app.config import get_settings

    get_settings.cache_clear()
    from fastapi_app.main import create_app

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("service") == "rideauto-fastapi"
