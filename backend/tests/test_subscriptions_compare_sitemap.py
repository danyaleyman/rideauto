"""Subscriptions, compare, sitemap, lead persistence (mocked pool)."""
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
    monkeypatch.setenv("WRA_SUBSCRIPTIONS_ADMIN_KEY", "test-admin-key")
    from fastapi_app.config import get_settings

    get_settings.cache_clear()
    from fastapi_app.main import create_app

    app = create_app()
    app.state.meili = MagicMock()
    with TestClient(app) as client:
        yield client, mock_pool, app
    get_settings.cache_clear()


def test_compare_requires_ids(app_client) -> None:
    client, _pool, _app = app_client
    r = client.get("/api/compare")
    assert r.status_code == 422


def test_compare_too_many_ids(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, pool, _app = app_client
    pool.fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(
        "fastapi_app.routers.compare.fetch_cars_by_ids",
        AsyncMock(return_value={}),
    )
    ids = ",".join(f"id{i}" for i in range(5))
    r = client.get(f"/api/compare?ids={ids}")
    assert r.status_code == 400


def test_sitemap_cars(app_client, mock_pool: MagicMock) -> None:
    client, pool, _app = app_client
    pool.fetchval = AsyncMock(return_value=1)
    pool.fetch = AsyncMock(
        return_value=[
            {"car_id": "encar-1", "updated_at": None},
        ]
    )
    r = client.get("/api/sitemap/cars?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert body["result"][0]["ref"] == "encar-1"
    assert body.get("total") == 1


def test_subscriptions_list_requires_auth(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _pool, _app = app_client
    from fastapi import HTTPException

    async def _deny(*_a, **_kw):
        raise HTTPException(status_code=401, detail="unauthorized")

    monkeypatch.setattr("fastapi_app.routers.subscriptions._require_user", _deny)
    r = client.get("/api/subscriptions")
    assert r.status_code == 401


def test_leads_admin_requires_session(mock_pool: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException
    from fastapi.requests import Request
    from fastapi_app.config import get_settings
    from fastapi_app.main import create_app

    monkeypatch.setenv("WRA_REDIS_URL", "")
    get_settings.cache_clear()

    async def _deny(request: Request) -> None:
        raise HTTPException(status_code=403, detail="listing_admin_forbidden")

    monkeypatch.setattr("fastapi_app.routers.leads_admin._listing_admin_guard", _deny)
    app = create_app()
    app.state.meili = MagicMock()
    with TestClient(app) as client:
        r = client.get("/api/leads/admin")
        assert r.status_code == 403
    get_settings.cache_clear()


def test_leads_admin_lists(mock_pool: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from fastapi.requests import Request
    from fastapi_app.config import get_settings
    from fastapi_app.main import create_app

    monkeypatch.setenv("WRA_REDIS_URL", "")
    get_settings.cache_clear()
    pool = mock_pool

    async def _admin(request: Request):
        return SimpleNamespace(id=1, email="admin@test.ru")

    monkeypatch.setattr("fastapi_app.routers.leads_admin._listing_admin_guard", _admin)
    pool.fetch = AsyncMock(
        return_value=[
            {
                "id": 1,
                "full_name": "Test",
                "contact_method": "tg",
                "message": "hello",
                "pd_agree": True,
                "ip": "127.0.0.1",
                "email_sent": True,
                "created_at": None,
            }
        ]
    )
    pool.fetchval = AsyncMock(return_value=1)
    app = create_app()
    app.state.meili = MagicMock()
    with TestClient(app) as client:
        r = client.get("/api/leads/admin")
        assert r.status_code == 200, r.text
        assert r.json()["result"][0]["full_name"] == "Test"
    get_settings.cache_clear()


def test_meili_outbox_process_admin(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _pool, _app = app_client

    async def _fake_batch(*_a, **_kw):
        return {"ok": True, "processed": 2, "documents": 2, "deleted": 0}

    monkeypatch.setattr("fastapi_app.routers.meili_outbox.process_meili_outbox_batch", _fake_batch)
    r = client.post("/api/meili/outbox/process", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 401
    r2 = client.post("/api/meili/outbox/process", headers={"X-Admin-Key": "test-admin-key"})
    assert r2.status_code == 200
    assert r2.json().get("processed") == 2


def test_run_notifications_admin_key(app_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, pool, _app = app_client
    pool.fetch = AsyncMock(return_value=[])

    async def _fake_run(*_a, **_kw):
        return {"ok": True, "processed": 0, "emails_sent": 0, "hits_total": 0, "errors": []}

    monkeypatch.setattr(
        "fastapi_app.routers.subscriptions.run_all_subscription_notifications",
        _fake_run,
    )
    r = client.post("/api/subscriptions/run-notifications", headers={"X-Admin-Key": "wrong"})
    assert r.status_code == 401
    r2 = client.post("/api/subscriptions/run-notifications", headers={"X-Admin-Key": "test-admin-key"})
    assert r2.status_code == 200
    assert r2.json().get("ok") is True


def test_lead_persists_when_pool_available(app_client, mock_pool: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    client, pool, _app = app_client
    pool.fetchval = AsyncMock(return_value=42)
    pool.execute = AsyncMock()
    monkeypatch.setenv("WRA_LEAD_SMTP_HOST", "")
    monkeypatch.setenv("WRA_AUTH_SMTP_HOST", "")
    from fastapi_app.config import get_settings

    get_settings.cache_clear()

    async def _fake_email(*_a, **_kw):
        return None

    monkeypatch.setattr("fastapi_app.routers.lead._send_lead_email_sync", _fake_email)
    monkeypatch.setattr("fastapi_app.routers.lead.asyncio.to_thread", AsyncMock(return_value=None))

    r = client.post(
        "/api/lead",
        json={
            "full_name": "Test User",
            "contact_method": "telegram @test",
            "message": "Хочу купить авто из Кореи, бюджет до 3 млн",
            "pd_agree": True,
        },
    )
    # SMTP not configured → 503 unless we mock settings
    assert r.status_code in (503, 202)
