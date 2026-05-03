"""Разрешение DSN Postgres для скрейперов Encar и savers."""

from __future__ import annotations

import os
import urllib.parse
from typing import Any, Dict


def rewrite_postgres_hostname_for_host(dsn: str) -> str:
    """
    На VPS процесс идёт на хосте, а ``DATABASE_URL`` часто копируют из compose (``@postgres:5432``).
    Имя ``postgres`` резолвится только в docker-сети — с хоста подставляем ``127.0.0.1``.

    В контейнере ``api`` задайте ``WRA_PG_DSN_SKIP_HOST_REWRITE=1`` (см. docker-compose.yml).
    """
    if (os.environ.get("WRA_PG_DSN_SKIP_HOST_REWRITE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return dsn
    s = (dsn or "").strip()
    if not s:
        return s
    p = urllib.parse.urlsplit(s)
    if not p.hostname or str(p.hostname).lower() != "postgres":
        return s
    port = p.port if p.port is not None else 5432
    auth = ""
    if p.username:
        uq = urllib.parse.quote(p.username, safe="")
        if p.password is not None:
            uq += ":" + urllib.parse.quote(p.password, safe="")
        auth = uq + "@"
    netloc = f"{auth}127.0.0.1:{port}"
    return urllib.parse.urlunsplit((p.scheme, netloc, p.path, p.query, p.fragment))


def resolve_scraper_postgres_dsn(config: Dict[str, Any]) -> str:
    """
    DSN общий для чекпоинта и PostgresCarSaver.

    Если выставить **RIDEAUTO_PG_CHECKPOINT_DSN** — используется только он (поверх любых строк в YAML),
    нужно например когда на хосте в ``scraper_config.local.yaml`` остался hostname ``postgres`` из compose.

    Иначе порядок: ``checkpoint.postgres.dsn`` → ``storage.postgres.dsn`` → ``DATABASE_URL``.
    """
    ovr = (os.environ.get("RIDEAUTO_PG_CHECKPOINT_DSN") or "").strip()
    if ovr:
        return rewrite_postgres_hostname_for_host(ovr)
    cp = config.get("checkpoint", {}) or {}
    pg_cp = cp.get("postgres")
    if isinstance(pg_cp, dict):
        d = str(pg_cp.get("dsn") or "").strip()
        if d:
            return rewrite_postgres_hostname_for_host(d)
    storage_cfg = config.get("storage", {}) or {}
    d = str((storage_cfg.get("postgres") or {}).get("dsn") or "").strip()
    if d:
        return rewrite_postgres_hostname_for_host(d)
    return rewrite_postgres_hostname_for_host((os.environ.get("DATABASE_URL") or "").strip())
