from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from fastapi_app.catalog_enrich_pg import enrich_rows_pg_term_cache


class _AcquireCM:
    def __init__(self, conn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        return None


@pytest.mark.asyncio
async def test_pg_cache_readonly_fills_ru():
    rows = [
        {
            "text_in": "some-ko-color",
            "domain": "color",
            "ru": "",
            "en": "Grey",
            "source_ru": "none",
        }
    ]

    conn = type("Conn", (), {})()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "source_text": "some-ko-color",
                "source_lang": "ko",
                "domain": "color",
                "target_lang": "ru",
                "translated_text": "PG_RU_VALUE",
            }
        ]
    )

    pool = type("Pool", (), {})()

    def _acquire():
        return _AcquireCM(conn)

    pool.acquire = _acquire

    with patch("fastapi_app.catalog_enrich_pg.detect_lang", return_value="ko"):
        out = await enrich_rows_pg_term_cache(pool, rows, timeout_sec=2.0, max_keys=50, max_rounds=5)

    assert out.hits_ru == 1
    assert out.truncated is False
    assert out.rounds_executed >= 1
    assert rows[0]["ru"] == "PG_RU_VALUE"
    assert rows[0]["source_ru"] == "postgres_term_cache"
    assert conn.fetch.await_count == 1


@pytest.mark.asyncio
async def test_pg_truncated_when_round_budget_tight():
    # en заполнен, чтобы ключи генерировались только для RU (по строке два target — ru+en — удвоили бы UNNEST).
    rows = [
        {"text_in": "c0", "domain": "color", "ru": "", "en": "E0", "source_ru": "none"},
        {"text_in": "c1", "domain": "color", "ru": "", "en": "E1", "source_ru": "none"},
        {"text_in": "c2", "domain": "color", "ru": "", "en": "E2", "source_ru": "none"},
        {"text_in": "c3", "domain": "color", "ru": "", "en": "E3", "source_ru": "none"},
    ]
    conn = type("Conn", (), {})()
    conn.fetch = AsyncMock(return_value=[])
    pool = type("Pool", (), {})()
    pool.acquire = lambda: _AcquireCM(conn)

    with patch("fastapi_app.catalog_enrich_pg.detect_lang", return_value="ko"):
        out_a = await enrich_rows_pg_term_cache(pool, rows, timeout_sec=2.0, max_keys=2, max_rounds=1)

    assert out_a.truncated is True
    assert out_a.keys_queried == 2
    assert out_a.rounds_executed == 1
    assert conn.fetch.await_count == 1

    conn.fetch.reset_mock()

    with patch("fastapi_app.catalog_enrich_pg.detect_lang", return_value="ko"):
        rows2 = [
            {"text_in": "c0", "domain": "color", "ru": "", "en": "E0", "source_ru": "none"},
            {"text_in": "c1", "domain": "color", "ru": "", "en": "E1", "source_ru": "none"},
            {"text_in": "c2", "domain": "color", "ru": "", "en": "E2", "source_ru": "none"},
            {"text_in": "c3", "domain": "color", "ru": "", "en": "E3", "source_ru": "none"},
        ]
        out_b = await enrich_rows_pg_term_cache(pool, rows2, timeout_sec=2.0, max_keys=2, max_rounds=3)

    assert out_b.truncated is False
    assert out_b.keys_queried == 4
    assert conn.fetch.await_count == 2
