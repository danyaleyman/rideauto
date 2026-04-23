from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from fastapi_app.config import get_settings

router = APIRouter(tags=["translate"])

_CACHE_MAX = 1024
_TRANSLATE_CACHE: "OrderedDict[str, str]" = OrderedDict()


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    target_lang: Literal["ru"] = "ru"
    provider: Literal["openai", "deepseek"] | None = None
    domain: str = Field(default="inspection_comment", max_length=128)


class TranslateResponse(BaseModel):
    translated_text: str
    provider: str
    model: str
    cached: bool = False


def _cache_get(key: str) -> str | None:
    val = _TRANSLATE_CACHE.get(key)
    if val is None:
        return None
    _TRANSLATE_CACHE.move_to_end(key)
    return val


def _cache_put(key: str, value: str) -> None:
    _TRANSLATE_CACHE[key] = value
    _TRANSLATE_CACHE.move_to_end(key)
    while len(_TRANSLATE_CACHE) > _CACHE_MAX:
        _TRANSLATE_CACHE.popitem(last=False)


def _build_chat_url(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return ""
    if b.endswith("/chat/completions"):
        return b
    return f"{b}/chat/completions"


def _provider_config(provider: str) -> tuple[str, str]:
    settings = get_settings()
    p = (provider or settings.translate_provider or "openai").strip().lower()
    if p == "deepseek":
        return settings.translate_deepseek_base_url, settings.translate_deepseek_model
    return settings.translate_openai_base_url, settings.translate_openai_model


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(payload: TranslateRequest) -> TranslateResponse:
    settings = get_settings()
    api_key = (settings.translate_api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="translation api key is not configured")

    provider = (payload.provider or settings.translate_provider or "openai").strip().lower()
    base_url, model = _provider_config(provider)
    chat_url = _build_chat_url(base_url)
    if not chat_url:
        raise HTTPException(status_code=500, detail="translation provider url is empty")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="empty text")

    cache_key = hashlib.sha256(f"{provider}|{model}|{payload.target_lang}|{text}".encode("utf-8")).hexdigest()
    cached = _cache_get(cache_key)
    if cached:
        return TranslateResponse(
            translated_text=cached,
            provider=provider,
            model=model,
            cached=True,
        )

    system_prompt = (
        "Translate user text to Russian. Keep meaning precise, keep numbers/dates/VIN/codes intact, "
        "do not add explanations, return plain translated text only."
    )
    req_body = {
        "model": model,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.translate_timeout_sec, trust_env=False) as client:
            resp = await client.post(chat_url, headers=headers, json=req_body)
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"translation upstream error: {resp.status_code}")
            data = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"translation request failed: {e}") from e

    out = ""
    try:
        out = str(data["choices"][0]["message"]["content"]).strip()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"translation response parse failed: {e}") from e
    if not out:
        raise HTTPException(status_code=502, detail="translation returned empty text")

    _cache_put(cache_key, out)
    return TranslateResponse(
        translated_text=out,
        provider=provider,
        model=model,
        cached=False,
    )
