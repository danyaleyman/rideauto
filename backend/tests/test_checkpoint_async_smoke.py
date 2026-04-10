"""Локальный smoke: CheckpointAsync сериализует вызовы (mock, без Postgres)."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_checkpoint_async_mock_smoke() -> None:
    with patch("scraper_pipeline.checkpoint_pg.Checkpoint") as MockCP:
        inst = MagicMock()
        inst.is_collected = MagicMock(return_value=False)
        inst.pending_count = MagicMock(return_value=42)
        inst.pop_pending_batch = MagicMock(return_value=[])
        inst.connect = MagicMock()
        inst.close = MagicMock()
        MockCP.return_value = inst

        from scraper_pipeline.checkpoint_pg import CheckpointAsync

        cp = CheckpointAsync(dsn="postgresql://mock", scope="encar")
        await cp.connect()
        assert await cp.is_collected("x") is False
        assert await cp.pending_count() == 42
        assert inst.is_collected.call_count >= 1
        await cp.close()


def test_import_encar_modules() -> None:
    from scraper_pipeline.encar import workers  # noqa: F401
    from encar_scraper import run_scraper  # noqa: F401

    assert inspect.iscoroutinefunction(run_scraper)
