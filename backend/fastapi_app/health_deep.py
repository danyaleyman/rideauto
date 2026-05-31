"""Глубокая проверка зависимостей API (PG, Redis, Meilisearch) + метрики для алертов."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi_app.config import Settings


def _meili_index_name(settings: Settings) -> str:
    return (settings.meilisearch_index or "cars").strip() or "cars"


async def check_postgres(pg_pool) -> dict[str, Any]:
    try:
        row = await pg_pool.fetchrow(
            """
            SELECT
                COUNT(*)::bigint AS total,
                COUNT(*) FILTER (WHERE dedupe_canonical_car_id IS NULL)::bigint AS indexable,
                MAX(updated_at) AS max_updated_at
            FROM cars
            """
        )
        total = int(row["total"] or 0)
        indexable = int(row["indexable"] or 0)
        return {
            "ok": True,
            "cars_total": total,
            "cars_indexable": indexable,
            "max_updated_at": row["max_updated_at"].isoformat() if row["max_updated_at"] else None,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


async def check_redis(redis_client) -> dict[str, Any]:
    if redis_client is None:
        return {"ok": True, "configured": False}
    try:
        pong = await redis_client.ping()
        return {"ok": bool(pong), "configured": True}
    except Exception as exc:
        return {"ok": False, "configured": True, "error": str(exc)[:200]}


async def check_meilisearch(meili_client, settings: Settings, pg_indexable: int) -> dict[str, Any]:
    index = _meili_index_name(settings)
    min_pct = float(settings.health_meili_min_coverage_pct)
    try:
        stats = await asyncio.to_thread(meili_client.index(index).get_stats)
        docs = int(getattr(stats, "number_of_documents", 0) or 0)
        ratio = (docs / pg_indexable) if pg_indexable > 0 else 1.0
        ok = pg_indexable == 0 or ratio >= (min_pct / 100.0)
        return {
            "ok": ok,
            "index": index,
            "documents": docs,
            "pg_indexable": pg_indexable,
            "coverage_ratio": round(ratio, 4),
            "min_coverage_pct": min_pct,
            "stale": not ok,
        }
    except Exception as exc:
        return {"ok": False, "index": index, "error": str(exc)[:200], "stale": True}


async def run_deep_health(
    *,
    pg_pool,
    redis_client,
    meili_client,
    settings: Settings,
) -> dict[str, Any]:
    pg = await check_postgres(pg_pool)
    redis = await check_redis(redis_client)
    pg_indexable = int(pg.get("cars_indexable") or 0) if pg.get("ok") else 0
    meili = await check_meilisearch(meili_client, settings, pg_indexable)

    checks = {"postgres": pg, "redis": redis, "meilisearch": meili}
    pg_ok = bool(pg.get("ok"))
    redis_ok = not redis.get("configured") or bool(redis.get("ok"))
    meili_ok = bool(meili.get("ok"))

    if not pg_ok or not redis_ok:
        status = "unhealthy"
    elif meili.get("stale") or not meili_ok:
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "checks": checks,
        "redis_cache": redis_client is not None,
    }


def update_health_metrics(payload: dict[str, Any]) -> None:
    """Обновить Prometheus-гейджи (no-op если prometheus_client недоступен)."""
    try:
        from prometheus_client import Gauge
    except ImportError:
        return

    checks = payload.get("checks") or {}
    pg = checks.get("postgres") or {}
    meili = checks.get("meilisearch") or {}

    g_ok = Gauge("wra_health_ok", "1 if deep health status is ok")
    g_pg = Gauge("wra_health_pg_cars_indexable", "Cars eligible for Meili index")
    g_meili = Gauge("wra_health_meili_documents", "Meilisearch index document count")
    g_ratio = Gauge("wra_health_meili_coverage_ratio", "meili_docs / pg_indexable")

    status = payload.get("status")
    g_ok.set(1 if status == "ok" else 0)
    if pg.get("ok"):
        g_pg.set(float(pg.get("cars_indexable") or 0))
    if meili.get("ok") or meili.get("documents") is not None:
        g_meili.set(float(meili.get("documents") or 0))
        g_ratio.set(float(meili.get("coverage_ratio") or 0))
