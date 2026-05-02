"""Разрешение DSN Postgres для скрейперов Encar и savers."""

from __future__ import annotations

import os
from typing import Any, Dict


def resolve_scraper_postgres_dsn(config: Dict[str, Any]) -> str:
    """
    DSN общий для чекпоинта и PostgresCarSaver.

    Если выставить **RIDEAUTO_PG_CHECKPOINT_DSN** — используется только он (поверх любых строк в YAML),
    нужно например когда на хосте в ``scraper_config.local.yaml`` остался hostname ``postgres`` из compose.

    Иначе порядок: ``checkpoint.postgres.dsn`` → ``storage.postgres.dsn`` → ``DATABASE_URL``.
    """
    ovr = (os.environ.get("RIDEAUTO_PG_CHECKPOINT_DSN") or "").strip()
    if ovr:
        return ovr
    cp = config.get("checkpoint", {}) or {}
    pg_cp = cp.get("postgres")
    if isinstance(pg_cp, dict):
        d = str(pg_cp.get("dsn") or "").strip()
        if d:
            return d
    storage_cfg = config.get("storage", {}) or {}
    d = str((storage_cfg.get("postgres") or {}).get("dsn") or "").strip()
    if d:
        return d
    return (os.environ.get("DATABASE_URL") or "").strip()
