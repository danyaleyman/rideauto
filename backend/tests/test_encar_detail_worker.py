"""Локальные проверки detail_worker: таймаут деталя и успешный путь (без сети)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from scraper_pipeline.encar.workers import detail_worker


@pytest.mark.asyncio
async def test_detail_worker_outer_timeout_increments_detail_fail() -> None:
    log = logging.getLogger("test_encar")
    stats: dict[str, Any] = {
        "processed": 0,
        "saved": 0,
        "detail_gone": 0,
        "detail_fail": 0,
        "parse_fail": 0,
        "_save_baseline": None,
    }
    queue: asyncio.Queue = asyncio.Queue()
    client = MagicMock()
    async def _hang(*_a: Any, **_k: Any) -> Any:
        await asyncio.sleep(30)

    client.fetch_vehicle_detail = AsyncMock(side_effect=_hang)

    checkpoint = MagicMock()
    checkpoint.is_collected = AsyncMock(return_value=False)
    checkpoint.mark_collected = AsyncMock()
    checkpoint.add_pending = AsyncMock(return_value=True)

    saver = MagicMock()
    saver.save_car = AsyncMock()

    parser = MagicMock()

    config = {
        "http": {"detail_wall_timeout_sec": 0.2, "detail_extras_wall_timeout_sec": 2, "parse_wall_timeout_sec": 5},
        "max_new_saves_per_run": 0,
    }

    await queue.put(("1", "for", {"Id": "1"}))
    await queue.put(None)

    await detail_worker(0, client, checkpoint, saver, parser, config, queue, stats, log, max_cars=0, stats_lock=None)

    assert stats["detail_fail"] == 1
    assert stats["processed"] == 0
    saver.save_car.assert_not_called()
    checkpoint.add_pending.assert_awaited_once()


@pytest.mark.asyncio
async def test_detail_worker_success_increments_processed() -> None:
    log = logging.getLogger("test_encar")
    stats: dict[str, Any] = {
        "processed": 0,
        "saved": 0,
        "detail_gone": 0,
        "detail_fail": 0,
        "parse_fail": 0,
        "_save_baseline": None,
    }
    queue: asyncio.Queue = asyncio.Queue()

    detail = {
        "vehicleNo": None,
        "advertisement": {},
        "photos": [],
        "condition": {},
    }

    client = MagicMock()
    client.fetch_vehicle_detail = AsyncMock(return_value=(detail, 200, None))
    client.fetch_record = AsyncMock(return_value=(None, 404, None))
    client.fetch_diagnosis = AsyncMock(return_value=(None, 404, None))
    client.fetch_inspection = AsyncMock(return_value=(None, 404, None))
    client.fetch_sellingpoint = AsyncMock(return_value=(None, 404, None))
    client.fetch_user = AsyncMock(return_value=(None, 404, None))

    checkpoint = MagicMock()
    checkpoint.is_collected = AsyncMock(return_value=False)
    checkpoint.mark_collected = AsyncMock()

    saver = MagicMock()
    saver.save_car = AsyncMock()

    parser = MagicMock()
    parser.parse_inspection = MagicMock(return_value={})
    parser.normalize_car = MagicMock(
        return_value={"data": {"title": "x"}, "meta": {}},
    )

    config = {
        "http": {
            "detail_wall_timeout_sec": 5,
            "detail_extras_wall_timeout_sec": 5,
            "parse_wall_timeout_sec": 5,
        },
        "max_new_saves_per_run": 0,
    }

    await queue.put(("99", "for", {"Id": "99"}))
    await queue.put(None)

    await detail_worker(0, client, checkpoint, saver, parser, config, queue, stats, log, max_cars=0, stats_lock=None)

    assert stats["processed"] == 1
    assert stats["saved"] == 1
    saver.save_car.assert_called_once()


@pytest.mark.asyncio
async def test_detail_fail_transient_status_requeues() -> None:
    log = logging.getLogger("test_encar")
    stats: dict[str, Any] = {
        "processed": 0,
        "saved": 0,
        "detail_gone": 0,
        "detail_fail": 0,
        "parse_fail": 0,
        "_save_baseline": None,
    }
    queue: asyncio.Queue = asyncio.Queue()
    client = MagicMock()
    client.fetch_vehicle_detail = AsyncMock(return_value=({}, 503, "err"))
    client.fetch_record = AsyncMock(return_value=(None, 404, None))
    client.fetch_diagnosis = AsyncMock(return_value=(None, 404, None))
    client.fetch_inspection = AsyncMock(return_value=(None, 404, None))
    client.fetch_sellingpoint = AsyncMock(return_value=(None, 404, None))

    checkpoint = MagicMock()
    checkpoint.is_collected = AsyncMock(return_value=False)
    checkpoint.mark_collected = AsyncMock()
    checkpoint.add_pending = AsyncMock(return_value=True)

    saver = MagicMock()
    parser = MagicMock()

    config = {
        "http": {"detail_wall_timeout_sec": 5, "detail_extras_wall_timeout_sec": 2, "parse_wall_timeout_sec": 5},
        "max_new_saves_per_run": 0,
    }

    await queue.put(("7", "for", {"Id": "7"}))
    await queue.put(None)

    await detail_worker(0, client, checkpoint, saver, parser, config, queue, stats, log, max_cars=0, stats_lock=None)

    assert stats["detail_fail"] == 1
    checkpoint.add_pending.assert_awaited_once()
    saver.save_car.assert_not_called()


@pytest.mark.asyncio
async def test_detail_404_marks_collected_no_requeue() -> None:
    log = logging.getLogger("test_encar")
    stats: dict[str, Any] = {
        "processed": 0,
        "saved": 0,
        "detail_gone": 0,
        "detail_fail": 0,
        "parse_fail": 0,
        "_save_baseline": None,
    }
    queue: asyncio.Queue = asyncio.Queue()
    client = MagicMock()
    client.fetch_vehicle_detail = AsyncMock(return_value=(None, 404, None))

    checkpoint = MagicMock()
    checkpoint.is_collected = AsyncMock(return_value=False)
    checkpoint.mark_collected = AsyncMock()
    checkpoint.add_pending = AsyncMock(return_value=True)

    saver = MagicMock()
    parser = MagicMock()
    config = {"http": {"detail_wall_timeout_sec": 5}, "max_new_saves_per_run": 0}

    await queue.put(("8", "for", {"Id": "8"}))
    await queue.put(None)

    await detail_worker(0, client, checkpoint, saver, parser, config, queue, stats, log, max_cars=0, stats_lock=None)

    assert stats["detail_gone"] == 1
    checkpoint.mark_collected.assert_awaited_once_with("8")
    checkpoint.add_pending.assert_not_called()


@pytest.mark.asyncio
async def test_max_new_cap_requeues_without_save() -> None:
    log = logging.getLogger("test_encar")
    stats: dict[str, Any] = {
        "processed": 0,
        "saved": 102,
        "detail_gone": 0,
        "detail_fail": 0,
        "parse_fail": 0,
        "_save_baseline": 100,
    }
    queue: asyncio.Queue = asyncio.Queue()
    client = MagicMock()
    client.fetch_vehicle_detail = AsyncMock()

    checkpoint = MagicMock()
    checkpoint.is_collected = AsyncMock(return_value=False)
    checkpoint.add_pending = AsyncMock()

    saver = MagicMock()
    parser = MagicMock()

    config = {"http": {}, "max_new_saves_per_run": 0}

    await queue.put(("1", "for", {"Id": "1"}))
    await queue.put(None)

    config["max_new_saves_per_run"] = 2
    await detail_worker(0, client, checkpoint, saver, parser, config, queue, stats, log, max_cars=0, stats_lock=None)

    client.fetch_vehicle_detail.assert_not_called()
    checkpoint.add_pending.assert_called_once()
    assert stats["processed"] == 0
