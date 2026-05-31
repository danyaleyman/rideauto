"""Web Push API (VAPID + subscribe)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def mock_pool(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    pool = MagicMock()
    pool.close = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchval = AsyncMock(return_value=0)
    pool.execute = AsyncMock()

    async def _create_pool(*_a, **_kw):
        return pool

    monkeypatch.setattr("fastapi_app.main.asyncpg.create_pool", _create_pool)
    return pool


@pytest.fixture
def app_client(mock_pool: MagicMock, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WRA_REDIS_URL", "")
    from fastapi_app.config import get_settings

    get_settings.cache_clear()
    from fastapi_app.main import create_app

    app = create_app()
    app.state.meili = MagicMock()
    with TestClient(app) as client:
        yield client, mock_pool
    get_settings.cache_clear()


def test_vapid_public_key_not_configured(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _pool = app_client
    monkeypatch.setenv("WRA_PUSH_VAPID_PUBLIC_KEY", "")
    from fastapi_app.config import get_settings

    get_settings.cache_clear()
    r = client.get("/api/push/vapid-public-key")
    assert r.status_code == 503


def test_vapid_public_key_ok(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _pool = app_client
    monkeypatch.setenv("WRA_PUSH_VAPID_PUBLIC_KEY", "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U")
    from fastapi_app.config import get_settings

    get_settings.cache_clear()
    r = client.get("/api/push/vapid-public-key")
    assert r.status_code == 200
    assert "public_key" in r.json()


def test_push_subscribe_requires_auth(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _pool = app_client
    monkeypatch.setenv("WRA_PUSH_VAPID_PUBLIC_KEY", "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U")
    from fastapi import HTTPException
    from fastapi_app.config import get_settings

    async def _deny(*_a, **_kw):
        raise HTTPException(status_code=401, detail="unauthorized")

    monkeypatch.setattr("fastapi_app.routers.push._require_user", _deny)
    get_settings.cache_clear()
    r = client.post(
        "/api/push/subscribe",
        json={
            "endpoint": "https://push.example.com/sub/abc1234567890",
            "keys": {"p256dh": "x" * 20, "auth": "y" * 20},
        },
    )
    assert r.status_code == 401


def test_push_subscribe_ok(app_client, mock_pool: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    client, pool = app_client
    monkeypatch.setenv("WRA_PUSH_VAPID_PUBLIC_KEY", "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U")
    from fastapi_app.config import get_settings

    user = SimpleNamespace(id="user-1", email="u@example.com")

    async def _user(*_a, **_kw):
        return user

    monkeypatch.setattr("fastapi_app.routers.push._require_user", _user)
    get_settings.cache_clear()
    r = client.post(
        "/api/push/subscribe",
        json={
            "endpoint": "https://push.example.com/sub/abc1234567890",
            "keys": {"p256dh": "x" * 20, "auth": "y" * 20},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    pool.execute.assert_awaited()
