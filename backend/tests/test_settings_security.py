"""Валидации безопасности в Settings: CORS origins + prod fail-fast."""
from __future__ import annotations

import pytest

from fastapi_app.config import Settings


def _settings(**env: str) -> Settings:
    return Settings(**env)  # type: ignore[arg-type]


def test_cors_default_is_wildcard_in_dev() -> None:
    s = _settings(deployment_env="dev")
    assert s.cors_origins_list() == ["*"]


def test_cors_origins_parsed_and_trimmed() -> None:
    s = _settings(cors_allow_origins="https://rideauto.ru/, https://www.rideauto.ru ")
    assert s.cors_origins_list() == ["https://rideauto.ru", "https://www.rideauto.ru"]


def test_cors_wildcard_with_credentials_rejected() -> None:
    with pytest.raises(ValueError, match="несовместим"):
        _settings(cors_allow_origins="*", cors_allow_credentials=True)


def test_cors_explicit_with_credentials_allowed() -> None:
    s = _settings(
        cors_allow_origins="https://rideauto.ru",
        cors_allow_credentials=True,
    )
    assert s.cors_allow_credentials is True
    assert s.cors_origins_list() == ["https://rideauto.ru"]


def test_prod_rejects_wildcard_cors() -> None:
    with pytest.raises(ValueError, match="WRA_CORS_ALLOW_ORIGINS"):
        _settings(
            deployment_env="prod",
            pg_dsn="postgresql://wra:secret@db:5432/wra",
            auth_secret="x" * 32,
            cache_invalidate_secret="y" * 32,
            cors_allow_origins="*",
        )


def test_prod_accepts_explicit_cors() -> None:
    s = _settings(
        deployment_env="prod",
        pg_dsn="postgresql://wra:secret@db:5432/wra",
        auth_secret="x" * 32,
        cache_invalidate_secret="y" * 32,
        cors_allow_origins="https://rideauto.ru",
    )
    assert s.cors_origins_list() == ["https://rideauto.ru"]


def test_prod_rejects_default_pg_credentials() -> None:
    with pytest.raises(ValueError, match="WRA_PG_DSN"):
        _settings(
            deployment_env="prod",
            pg_dsn="postgresql://postgres:postgres@db:5432/wra",
            auth_secret="x" * 32,
            cache_invalidate_secret="y" * 32,
            cors_allow_origins="https://rideauto.ru",
        )
