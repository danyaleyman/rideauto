from __future__ import annotations

import asyncio
import logging

from scraper_pipeline.che168.workers import list_producer_che168


class _FakeClient:
    """Отдаёт страницы из `pages` (pageindex -> список лотов); отсутствующая страница = конец выдачи."""

    def __init__(self, pages: dict[int, list[dict]], fail: bool = False):
        self.pages = pages
        self.fail = fail
        self.calls: list[int] = []

    async def fetch_search(self, **kwargs):
        if self.fail:
            return None, 500, "boom"
        page = int(kwargs.get("pageindex", 1))
        self.calls.append(page)
        items = self.pages.get(page)
        if items is None:
            return {"returncode": 0, "result": {"list": []}}, 200, None
        return {"returncode": 0, "result": {"list": items}}, 200, None


class _FakeCheckpoint:
    def __init__(self) -> None:
        self.offsets: dict[str, int] = {}
        self.added: list[str] = []

    async def get_last_offset(self, key: str) -> int:
        return int(self.offsets.get(key, 0))

    async def set_last_offset(self, key: str, value: int) -> None:
        self.offsets[key] = int(value)

    async def is_collected(self, car_id: str) -> bool:
        return False

    async def add_pending_batch(self, items) -> int:
        self.added.extend([it[0] for it in items])
        return len(items)

    async def pending_count(self) -> int:
        return 0


def _config(**ch_overrides) -> dict:
    ch = {
        "brand_ids": [111],
        "search_pagination_mode": "pageindex",
        "search_pagesize": 20,
        "list_max_parallel": 1,
        "list_brand_parallel": 1,
        "segmentation": {"enabled": False},
    }
    ch.update(ch_overrides)
    return {
        "che168": ch,
        "http": {
            "list_page_delay_min": 0,
            "list_page_delay_max": 0,
            "list_stall_pages_limit": 40,
            "list_max_fail_streak": 3,
        },
    }


def _stats() -> dict:
    return {"list_pages": 0, "ids_discovered": 0, "ids_queued": 0, "che168_search_empty_breaks": 0}


def _run(client, checkpoint, config) -> None:
    asyncio.run(
        list_producer_che168(
            client,
            checkpoint,
            config,
            _stats(),
            logging.getLogger("test_che168_offset_reset"),
        )
    )


def test_offset_resets_to_head_when_brand_exhausted() -> None:
    client = _FakeClient({1: [{"id": "1001"}, {"id": "1002"}], 2: [{"id": "1003"}]})
    cp = _FakeCheckpoint()
    _run(client, cp, _config())

    assert client.calls == [1, 2, 3]  # страница 3 пустая => выдача кончилась
    assert cp.added == ["1001", "1002", "1003"]
    # Чекпоинт вернулся в начало, иначе новые лоты в «голове» выдачи не увидеть.
    assert cp.offsets["brand_111_page"] == 1


def test_offset_not_reset_when_disabled() -> None:
    client = _FakeClient({1: [{"id": "1001"}]})
    cp = _FakeCheckpoint()
    _run(client, cp, _config(reset_offset_on_complete=False))

    assert cp.offsets["brand_111_page"] == 2


def test_offset_not_reset_on_errors() -> None:
    client = _FakeClient({}, fail=True)
    cp = _FakeCheckpoint()
    _run(client, cp, _config())

    assert cp.offsets == {}


def test_segment_offset_resets_to_head_when_segment_exhausted() -> None:
    seg_cfg = {
        "enabled": True,
        "strategy": "price_x_year",
        "price_segments": [[0, 5000]],
        "year_segments": [[2000, 2005]],
        "segment_checkpoints": True,
    }
    client = _FakeClient({1: [{"id": "2001"}]})
    cp = _FakeCheckpoint()
    _run(client, cp, _config(segmentation=seg_cfg))

    key = "segment_111_price_0_5000_year_2000_2005_page"
    assert cp.added == ["2001"]
    assert cp.offsets[key] == 1
