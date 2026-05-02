from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

import fastapi_app.catalog_enrich_llm as enrich_llm
from fastapi_app.catalog_enrich_llm import openai_enrich_missing
from fastapi_app.config import Settings


@pytest.fixture(autouse=True)
def _clear_pair_cache():
    enrich_llm._PAIR_CACHE.clear()
    yield


def _settings_llm(**overrides):
    kwargs = dict(
        translate_api_key="test-key",
        translate_openai_base_url="https://api.openai.com/v1",
        catalog_enrich_llm_fallback=True,
        translate_timeout_sec=20.0,
        catalog_enrich_llm_max_items=24,
        catalog_enrich_openai_model="gpt-4o-mini",
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
        out, used = await openai_enrich_missing(rows, settings=settings, max_llm_items=12)

    assert used is True
    assert out[0]["ru"] == "New RU resolved"
    assert out[0]["en"] == "New EN"
    assert out[0]["source_ru"] == "openai_fallback"


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
        out, used = await openai_enrich_missing(rows, settings=settings, max_llm_items=12)

    assert used is False
    assert out[0]["ru"] == ""
