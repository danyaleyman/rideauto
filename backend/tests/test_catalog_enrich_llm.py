from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from fastapi_app.catalog_enrich_llm import openai_enrich_missing, reset_pair_memory_cache_for_tests
from fastapi_app.config import Settings


@pytest.fixture(autouse=True)
def _clear_pair_cache():
    reset_pair_memory_cache_for_tests()
    yield


def _settings_llm(**overrides):
    kwargs = dict(
        translate_api_key="test-key",
        translate_openai_base_url="https://api.openai.com/v1",
        catalog_enrich_llm_fallback=True,
        translate_timeout_sec=20.0,
        catalog_enrich_llm_max_items=24,
        catalog_enrich_openai_model="gpt-4o-mini",
        catalog_enrich_llm_retry_attempts=3,
        catalog_enrich_llm_retry_base_delay_sec=0.05,
        catalog_enrich_pair_redis_ttl_sec=3600,
    )
    kwargs.update(overrides)
    return Settings(**kwargs)


@pytest.mark.asyncio
async def test_openai_enrich_missing_fills_rows():
    settings = _settings_llm()
    rows = [
        {
            "text_in": "fixture-ko-ish",
            "domain": "generation",
            "ru": "",
            "en": "x",
            "source_ru": "none",
        }
    ]
    payload = dict(items=[dict(i=0, ru="New RU resolved", en="New EN")])
    body = json.dumps(payload, ensure_ascii=False)
    fake = {"choices": [{"message": {"content": body}}]}

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *a: object, **k: object):
            return httpx.Response(200, json=fake)

    with (
        patch("localization.term_localizer.detect_lang", return_value="ko"),
        patch("fastapi_app.catalog_enrich_llm.httpx.AsyncClient", FakeClient),
    ):
        oc = await openai_enrich_missing(rows, settings=settings, max_llm_items=12)

    assert oc.fallback_used is True
    assert oc.rows[0]["ru"] == "New RU resolved"
    assert oc.rows[0]["en"] == "New EN"
    assert oc.rows[0]["source_ru"] == "openai_fallback"
    assert oc.truncated is False
    assert oc.still_missing == 0


@pytest.mark.asyncio
async def test_openai_enrich_cached_avoids_repeat_post():
    settings = _settings_llm()

    rows_template = lambda: [
        {"text_in": "cache-key-here", "domain": "model", "ru": "", "en": "", "source_ru": "none"}
    ]
    payload = dict(items=[dict(i=0, ru="R1", en="E1")])
    body = json.dumps(payload, ensure_ascii=False)
    fake = {"choices": [{"message": {"content": body}}]}
    posts = 0

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *a: object, **k: object):
            nonlocal posts
            posts += 1
            return httpx.Response(200, json=fake)

    with (
        patch("localization.term_localizer.detect_lang", return_value="ko"),
        patch("fastapi_app.catalog_enrich_llm.httpx.AsyncClient", FakeClient),
    ):
        r1 = rows_template()
        await openai_enrich_missing(r1, settings=settings, max_llm_items=12)
        r2 = rows_template()
        await openai_enrich_missing(r2, settings=settings, max_llm_items=12)

    assert posts == 1
    assert r2[0]["ru"] == "R1"
    assert r2[0]["source_ru"] == "openai_fallback"


@pytest.mark.asyncio
async def test_openai_truncated_flag_three_candidates_two_batch():
    settings = _settings_llm(catalog_enrich_llm_max_items=2)
    rows = [
        {"text_in": "a1", "domain": "model", "ru": "", "en": "", "source_ru": "none"},
        {"text_in": "b2", "domain": "model", "ru": "", "en": "", "source_ru": "none"},
        {"text_in": "c3", "domain": "model", "ru": "", "en": "", "source_ru": "none"},
    ]
    payload = dict(
        items=[
            dict(i=0, ru="R0", en="E0"),
            dict(i=1, ru="R1", en="E1"),
        ]
    )
    body = json.dumps(payload, ensure_ascii=False)
    fake = {"choices": [{"message": {"content": body}}]}

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *a: object, **k: object):
            return httpx.Response(200, json=fake)

    with (
        patch("localization.term_localizer.detect_lang", return_value="ko"),
        patch("fastapi_app.catalog_enrich_llm.httpx.AsyncClient", FakeClient),
    ):
        oc = await openai_enrich_missing(rows, settings=settings, max_llm_items=2)

    assert oc.truncated is True
    assert oc.openai_batches_items == 2
    assert oc.still_missing >= 1
    assert oc.rows[0]["ru"]
    assert oc.rows[1]["ru"]
    assert not (oc.rows[2].get("ru") or "").strip()


@pytest.mark.asyncio
async def test_openai_enrich_missing_off_when_disabled():
    settings = _settings_llm(catalog_enrich_llm_fallback=False)
    rows = [{"text_in": "x", "domain": "generation", "ru": "", "en": "", "source_ru": "none"}]

    class BoomClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *a: object, **k: object):
            raise AssertionError("should not call OpenAI when fallback disabled")

    with patch("fastapi_app.catalog_enrich_llm.httpx.AsyncClient", BoomClient):
        oc = await openai_enrich_missing(rows, settings=settings, max_llm_items=12)

    assert oc.fallback_used is False
    assert oc.rows[0]["ru"] == ""
