"""DSN rewrite: compose hostname postgres → 127.0.0.1 on host runs."""

from __future__ import annotations

import os

import pytest

from scraper_pipeline.pg_dsn_resolve import (
    resolve_scraper_postgres_dsn,
    rewrite_postgres_hostname_for_host,
)


def test_rewrite_postgres_to_localhost():
    dsn = "postgresql://u:p@postgres:5432/wra"
    out = rewrite_postgres_hostname_for_host(dsn)
    assert "@127.0.0.1:5432/" in out
    assert "postgres" not in out.split("@")[1].split("/")[0]


def test_rewrite_skipped_when_env_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WRA_PG_DSN_SKIP_HOST_REWRITE", "1")
    dsn = "postgresql://u:p@postgres:5432/wra"
    assert rewrite_postgres_hostname_for_host(dsn) == dsn


def test_resolve_uses_database_url_and_rewrites(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("WRA_PG_DSN_SKIP_HOST_REWRITE", raising=False)
    monkeypatch.delenv("RIDEAUTO_PG_CHECKPOINT_DSN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://wra:wra@postgres:5432/wra")
    dsn = resolve_scraper_postgres_dsn({"storage": {"postgres": {"dsn": ""}}})
    assert "127.0.0.1" in dsn
    assert "postgres" not in dsn.split("@")[1].split("/")[0]
