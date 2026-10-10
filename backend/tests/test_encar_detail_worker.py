"""Локальные проверки detail_worker: таймаут деталя и успешный путь (без сети)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from scraper_pipeline.encar.workers import _detail_zero_fail_backoff, detail_worker


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
    client.policy = None  # detail_worker читает policy у клиента (resilience)
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
    client.policy = None
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
    client.policy = None
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
    client.policy = None
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
    client.policy = None
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


@pytest.mark.asyncio
async def test_detail_worker_flushes_buffer_with_bulk_save() -> None:
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

    detail = {"vehicleNo": None, "advertisement": {}, "photos": [], "condition": {}}
    client = MagicMock()
    client.policy = None
    client.fetch_vehicle_detail = AsyncMock(return_value=(detail, 200, None))
    client.fetch_record = AsyncMock(return_value=(None, 404, None))
    client.fetch_diagnosis = AsyncMock(return_value=(None, 404, None))
    client.fetch_inspection = AsyncMock(return_value=(None, 404, None))
    client.fetch_sellingpoint = AsyncMock(return_value=(None, 404, None))
    client.fetch_user = AsyncMock(return_value=(None, 404, None))

    checkpoint = MagicMock()
    checkpoint.is_collected = AsyncMock(return_value=False)
    checkpoint.mark_collected = AsyncMock()
    checkpoint.add_pending = AsyncMock()

    saver = MagicMock()
    saver.save_car = AsyncMock()
    saver.bulk_save = AsyncMock(return_value=2)

    parser = MagicMock()
    parser.parse_inspection = MagicMock(return_value={})
    parser.normalize_car = MagicMock(return_value={"data": {"title": "x"}, "meta": {}})

    config = {
        "http": {
            "detail_wall_timeout_sec": 5,
            "detail_extras_wall_timeout_sec": 5,
            "parse_wall_timeout_sec": 5,
        },
        "batch": {"save_batch_size": 2, "save_flush_sec": 999},
        "max_new_saves_per_run": 0,
    }

    await queue.put(("201", "for", {"Id": "201"}))
    await queue.put(("202", "for", {"Id": "202"}))
    await queue.put(None)

    await detail_worker(0, client, checkpoint, saver, parser, config, queue, stats, log, max_cars=0, stats_lock=None)

    assert stats["processed"] == 2
    assert stats["saved"] == 2
    saver.bulk_save.assert_awaited_once()
    saver.save_car.assert_not_called()
    assert checkpoint.mark_collected.await_count == 2


def _detail_payload_with_seller() -> dict:
    return {
        "vehicleNo": None,
        "advertisement": {},
        "photos": [],
        "condition": {},
        "item": [{"Separation": ["seller-1"]}],
    }


def _success_mocks(client: MagicMock, parser: MagicMock) -> None:
    client.policy = None
    client.fetch_record = AsyncMock(return_value=(None, 404, None))
    client.fetch_diagnosis = AsyncMock(return_value=(None, 404, None))
    client.fetch_inspection = AsyncMock(return_value=(None, 404, None))
    client.fetch_sellingpoint = AsyncMock(return_value=(None, 404, None))
    client.fetch_user = AsyncMock(return_value=({"id": "seller-1"}, 200, None))
    parser.parse_inspection = MagicMock(return_value={})
    parser.normalize_car = MagicMock(return_value={"data": {"title": "x"}, "meta": {}})


def _base_stats() -> dict:
    return {
        "processed": 0,
        "saved": 0,
        "detail_gone": 0,
        "detail_fail": 0,
        "parse_fail": 0,
        "_save_baseline": None,
    }


async def _run_one_detail(
    client: MagicMock,
    parser: MagicMock,
    config: dict,
    stats: dict,
    car_id: str = "99",
) -> MagicMock:
    """Прогон одного авто через detail_worker; возвращает мок-чекпоинт для ассертов."""
    log = logging.getLogger("test_encar")
    queue: asyncio.Queue = asyncio.Queue()
    checkpoint = MagicMock()
    checkpoint.is_collected = AsyncMock(return_value=False)
    checkpoint.mark_collected = AsyncMock()
    checkpoint.add_pending = AsyncMock(return_value=True)
    saver = MagicMock()
    saver.save_car = AsyncMock()
    await queue.put((car_id, "for", {"Id": car_id}))
    await queue.put(None)
    await detail_worker(0, client, checkpoint, saver, parser, config, queue, stats, log, max_cars=0, stats_lock=None)
    return checkpoint


def _http_cfg(**extra: Any) -> dict:
    cfg = {
        "detail_wall_timeout_sec": 5,
        "detail_extras_wall_timeout_sec": 5,
        "parse_wall_timeout_sec": 5,
    }
    cfg.update(extra)
    return cfg


@pytest.mark.asyncio
async def test_detail_worker_skips_user_extras_by_default() -> None:
    """`http.fetch_user_extras` по умолчанию false: /user/{Separation[0]} — 404 в 100 % карточек."""
    client = MagicMock()
    parser = MagicMock()
    _success_mocks(client, parser)
    client.fetch_vehicle_detail = AsyncMock(return_value=(_detail_payload_with_seller(), 200, None))
    stats = _base_stats()

    await _run_one_detail(
        client,
        parser,
        {"http": _http_cfg(), "max_new_saves_per_run": 0},
        stats,
    )

    assert stats["saved"] == 1
    client.fetch_user.assert_not_called()
    assert stats.get("endpoint_user_ok", 0) == 0
    assert stats.get("endpoint_user_fail", 0) == 0


@pytest.mark.asyncio
async def test_detail_worker_fetches_user_extras_when_enabled() -> None:
    client = MagicMock()
    parser = MagicMock()
    _success_mocks(client, parser)
    client.fetch_vehicle_detail = AsyncMock(return_value=(_detail_payload_with_seller(), 200, None))
    stats = _base_stats()

    await _run_one_detail(
        client,
        parser,
        {"http": _http_cfg(fetch_user_extras=True), "max_new_saves_per_run": 0},
        stats,
    )

    client.fetch_user.assert_awaited_once_with("seller-1")
    assert stats.get("endpoint_user_ok", 0) == 1


@pytest.mark.asyncio
async def test_detail_zero_fail_backoff_grows_and_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    d1 = await _detail_zero_fail_backoff(1, {})
    assert 0.8 <= d1 <= 1.2
    assert slept == [d1]

    d9 = await _detail_zero_fail_backoff(9, {})
    assert 12.0 <= d9 <= 15.0  # cap=15 c джиттером ±20 %

    d_custom = await _detail_zero_fail_backoff(
        10, {"detail_zero_fail_backoff_base_sec": 0.5, "detail_zero_fail_backoff_max_sec": 1.0}
    )
    assert 0.8 <= d_custom <= 1.0

    before = len(slept)
    assert await _detail_zero_fail_backoff(5, {"detail_zero_fail_backoff_base_sec": 0}) == 0.0
    assert len(slept) == before  # выключенный бэкофф не спит


@pytest.mark.asyncio
async def test_detail_worker_zero_status_backs_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """status=0 (нет HTTP-кода: открытый CB / мёртвый прокси) — воркер не должен крутиться без пауз."""
    slept: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    client = MagicMock()
    client.policy = None
    client.fetch_vehicle_detail = AsyncMock(return_value=(None, 0, "circuit_breaker_open"))
    parser = MagicMock()
    stats = _base_stats()

    checkpoint = await _run_one_detail(
        client,
        parser,
        {"http": _http_cfg(), "max_new_saves_per_run": 0},
        stats,
        car_id="11",
    )

    assert stats["detail_fail"] == 1
    assert checkpoint.add_pending.await_count == 1
    assert len(slept) == 1
    assert slept[0] > 0
