"""Unit-тесты deep health (без реальных PG/Meili)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from fastapi_app.config import Settings
from fastapi_app.health_deep import check_meilisearch, run_deep_health


@pytest.mark.asyncio
async def test_meili_stale_when_low_coverage() -> None:
    meili = MagicMock()
    meili.index.return_value.get_stats.return_value = MagicMock(number_of_documents=50)
    settings = Settings(health_meili_min_coverage_pct=90.0)
    out = await check_meilisearch(meili, settings, pg_indexable=100)
    assert out["ok"] is False
    assert out["stale"] is True
    assert out["coverage_ratio"] == 0.5


@pytest.mark.asyncio
async def test_run_deep_health_degraded_on_stale_meili() -> None:
    pg_pool = MagicMock()
    pg_pool.fetchrow = AsyncMock(
        return_value={"total": 100, "indexable": 100, "max_updated_at": None}
    )
    meili = MagicMock()
    meili.index.return_value.get_stats.return_value = MagicMock(number_of_documents=50)
    settings = Settings(health_meili_min_coverage_pct=90.0)

    payload = await run_deep_health(
        pg_pool=pg_pool,
        redis_client=None,
        meili_client=meili,
        settings=settings,
    )
    assert payload["status"] in ("degraded", "unhealthy")
    assert payload["checks"]["meilisearch"].get("stale") is True
