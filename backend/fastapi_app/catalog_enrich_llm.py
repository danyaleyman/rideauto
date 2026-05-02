"""
Опциональное дополнение enrich-ответа через OpenAI-совместимый Chat API — без Postgres, только HTTP.
Кэш: LRU в памяти + опционально Redis (тот же ключ по text+domain). Повторы не бьют сеть/OpenAI.

Ключ из env: Settings.translate_api_key (OPENAI_API_KEY / WRA_TRANSLATE_API_KEY).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

from fastapi_app.config import Settings
from fastapi_app.metrics.prometheus import (
    inc_cache_lookup,
    inc_catalog_enrich_llm_phase,
    observe_catalog_enrich_llm_http,
)

_PAIR_CACHE_MAX = 512
_PAIR_CACHE: OrderedDict[str, Tuple[str, str]] = OrderedDict()


def reset_pair_memory_cache_for_tests() -> None:
    """Только для тестов."""
    _PAIR_CACHE.clear()


@dataclass(frozen=True)
class CatalogEnrichLLMOutcome:
    rows: List[Dict[str, Any]]
    fallback_used: bool
    candidates: int
    memory_cache_hits: int
    redis_cache_hits: int
    openai_batches_items: int
    openai_ok: Optional[bool]
    truncated: bool
    still_missing: int


def _cache_sha(text: str, domain: str) -> str:
    return hashlib.sha256(f"{domain}\n{text}".encode("utf-8")).hexdigest()


def _pair_cache_get(text: str, domain: str) -> Optional[Tuple[str, str]]:
    k = _cache_sha(text, domain)
    v = _PAIR_CACHE.get(k)
    if v is None:
        return None
    _PAIR_CACHE.move_to_end(k)
    return v


def _pair_cache_put(text: str, domain: str, ru: str, en: str) -> None:
    k = _cache_sha(text, domain)
    _PAIR_CACHE[k] = (ru.strip(), en.strip())
    _PAIR_CACHE.move_to_end(k)
    while len(_PAIR_CACHE) > _PAIR_CACHE_MAX:
        _PAIR_CACHE.popitem(last=False)


def _redis_pair_key(prefix: str, text: str, domain: str) -> str:
    p = (prefix or "wra:api:cache").strip().rstrip(":")
    h = _cache_sha(text, domain)
    return f"{p}:catenrich:v1:{h}"


async def _pair_redis_get(
    redis: Optional[Any], prefix: str, text: str, domain: str
) -> Optional[Tuple[str, str]]:
    if redis is None:
        return None
    key = _redis_pair_key(prefix, text, domain)
    try:
        raw = await redis.get(key)
    except Exception:
        inc_cache_lookup("catalog_enrich_pair_redis", hit=False)
        return None
    if not raw:
        inc_cache_lookup("catalog_enrich_pair_redis", hit=False)
        return None
    try:
        blob = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        data = json.loads(blob)
        if not isinstance(data, dict):
            inc_cache_lookup("catalog_enrich_pair_redis", hit=False)
            return None
        ru = str(data.get("ru") or "").strip()
        en = str(data.get("en") or "").strip()
        hit = bool(ru or en)
        inc_cache_lookup("catalog_enrich_pair_redis", hit=hit)
        if not hit:
            return None
        return (ru, en)
    except Exception:
        inc_cache_lookup("catalog_enrich_pair_redis", hit=False)
        return None


async def _pair_redis_put(
    redis: Optional[Any],
    prefix: str,
    text: str,
    domain: str,
    ru: str,
    en: str,
    ttl_sec: int,
) -> None:
    if redis is None:
        return
    key = _redis_pair_key(prefix, text, domain)
    body = json.dumps({"ru": ru.strip(), "en": en.strip()}, ensure_ascii=False)
    try:
        await redis.set(key, body, ex=max(3600, int(ttl_sec)))
    except Exception:
        pass


def _chat_url(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return ""
    if b.endswith("/chat/completions"):
        return b
    return f"{b}/chat/completions"


def _row_eligible_for_llm(row: Dict[str, Any], detect_lang) -> bool:
    tin = (row.get("text_in") or "").strip()
    if not tin:
        return False
    ru = (row.get("ru") or "").strip()
    if ru:
        return False
    return detect_lang(tin) in ("ko", "zh")


async def _http_post_chat_completions_with_retry(
    *,
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    req_body: dict,
    max_attempts: int,
    base_delay: float,
) -> Tuple[Optional[httpx.Response], Optional[Exception]]:
    delay = float(base_delay)
    for attempt in range(max(1, max_attempts)):
        try:
            resp = await client.post(url, headers=headers, json=req_body)
        except httpx.RequestError as exc:
            last_net = exc
            if attempt >= max_attempts - 1:
                return None, exc
            await asyncio.sleep(delay)
            delay = min(delay * 2.0, 8.0)
            continue
        retryable_http = resp.status_code in (429, 502, 503, 504)
        if not retryable_http or attempt >= max_attempts - 1:
            return resp, None
        await asyncio.sleep(delay)
        delay = min(delay * 2.0, 8.0)
    raise RuntimeError("_http_post_chat_completions_with_retry exhausted without return")


async def openai_enrich_missing(
    rows: List[Dict[str, Any]],
    *,
    settings: Settings,
    max_llm_items: int,
    redis: Optional[Any] = None,
) -> CatalogEnrichLLMOutcome:
    """Дозаполнение пустого RU для KO/ZH строк: Redis → LRU → один batched OpenAI-запрос (с лимитом)."""
    from localization.term_localizer import detect_lang

    zeros = CatalogEnrichLLMOutcome(
        rows=rows,
        fallback_used=False,
        candidates=0,
        memory_cache_hits=0,
        redis_cache_hits=0,
        openai_batches_items=0,
        openai_ok=None,
        truncated=False,
        still_missing=0,
    )

    if not settings.catalog_enrich_llm_fallback:
        return zeros
    api_key = (settings.translate_api_key or "").strip()
    if not api_key:
        return zeros

    candidates_idx: List[int] = []
    for i, row in enumerate(rows):
        if _row_eligible_for_llm(row, detect_lang):
            candidates_idx.append(i)

    if not candidates_idx:
        inc_catalog_enrich_llm_phase("no_candidates")
        return CatalogEnrichLLMOutcome(
            rows=rows,
            fallback_used=False,
            candidates=0,
            memory_cache_hits=0,
            redis_cache_hits=0,
            openai_batches_items=0,
            openai_ok=None,
            truncated=False,
            still_missing=0,
        )

    mem_hits = 0
    redis_hits = 0
    redis_prefix = (settings.redis_cache_prefix or "wra:api:cache").strip().rstrip(":")

    for i in candidates_idx:
        row = rows[i]
        tin = (row.get("text_in") or "").strip()
        dom = (row.get("domain") or "").strip()

        rk = await _pair_redis_get(redis, redis_prefix, tin, dom)
        if rk:
            redis_hits += 1
            rr, ee = rk
            if rr:
                row["ru"] = rr
            if ee:
                row["en"] = ee
            row["source_ru"] = "openai_fallback"
            _pair_cache_put(tin, dom, rr, ee)
            continue

        ck = _pair_cache_get(tin, dom)
        if ck and (ck[0] or ck[1]):
            mem_hits += 1
            rr, ee = ck
            if rr:
                row["ru"] = rr
            if ee:
                row["en"] = ee
            row["source_ru"] = "openai_fallback"
            continue

    pending: List[Tuple[int, str, str]] = []
    for i in candidates_idx:
        row = rows[i]
        if (row.get("ru") or "").strip():
            continue
        tin = (row.get("text_in") or "").strip()
        dom = (row.get("domain") or "").strip()
        pending.append((i, tin, dom))

    truncated = len(pending) > max_llm_items
    pending_batch = pending[:max_llm_items]

    fb_used = bool(mem_hits or redis_hits) or any(
        r.get("source_ru") == "openai_fallback" for r in rows
    )

    if not pending_batch:
        inc_catalog_enrich_llm_phase("prefilled_only")
        still_missing = sum(
            1
            for i in candidates_idx
            if not (rows[i].get("ru") or "").strip()
        )
        return CatalogEnrichLLMOutcome(
            rows=rows,
            fallback_used=fb_used,
            candidates=len(candidates_idx),
            memory_cache_hits=mem_hits,
            redis_cache_hits=redis_hits,
            openai_batches_items=0,
            openai_ok=None,
            truncated=truncated,
            still_missing=still_missing,
        )

    payload_items = [{"i": a[0], "text": a[1], "domain": a[2]} for a in pending_batch]
    user_prompt = (
        "Return ONLY valid JSON with shape "
        '{"items":[{"i":<int>,"ru":<string>,"en":<string>},...]} '
        "matching the same indices i. "
        "translate Korean/Chinese car catalog facet strings to concise Russian (ru) and English (en) "
        "for website UI. Keep model codes (e.g. GV80, 2024). No explanations.\n\n"
        f"INPUT: {json.dumps({'items': payload_items}, ensure_ascii=False)}"
    )

    url = _chat_url(settings.translate_openai_base_url)
    if not url:
        inc_catalog_enrich_llm_phase("api_no_base_url")
        still_missing = sum(
            1 for i in candidates_idx if not (rows[i].get("ru") or "").strip()
        )
        return CatalogEnrichLLMOutcome(
            rows=rows,
            fallback_used=fb_used,
            candidates=len(candidates_idx),
            memory_cache_hits=mem_hits,
            redis_cache_hits=redis_hits,
            openai_batches_items=len(pending_batch),
            openai_ok=False,
            truncated=truncated,
            still_missing=still_missing,
        )

    model = (
        settings.catalog_enrich_openai_model or settings.translate_openai_model or "gpt-4o-mini"
    ).strip()
    req_body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You reply with compact JSON only. Keys in English."},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(
        connect=10.0,
        read=min(45.0, settings.translate_timeout_sec + 15),
        write=10.0,
        pool=5.0,
    )
    t0 = time.perf_counter()
    resp: Optional[httpx.Response] = None
    net_err: Optional[Exception] = None
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            resp, net_err = await _http_post_chat_completions_with_retry(
                client=client,
                url=url,
                headers=headers,
                req_body=req_body,
                max_attempts=max(1, settings.catalog_enrich_llm_retry_attempts),
                base_delay=max(0.05, settings.catalog_enrich_llm_retry_base_delay_sec),
            )
    finally:
        observe_catalog_enrich_llm_http(time.perf_counter() - t0)

    ttl = int(settings.catalog_enrich_pair_redis_ttl_sec)

    if net_err is not None:
        inc_catalog_enrich_llm_phase("api_network_fail")
        still_missing = sum(
            1 for i in candidates_idx if not (rows[i].get("ru") or "").strip()
        )
        return CatalogEnrichLLMOutcome(
            rows=rows,
            fallback_used=fb_used,
            candidates=len(candidates_idx),
            memory_cache_hits=mem_hits,
            redis_cache_hits=redis_hits,
            openai_batches_items=len(pending_batch),
            openai_ok=False,
            truncated=truncated,
            still_missing=still_missing,
        )

    if resp is None or resp.status_code >= 400:
        inc_catalog_enrich_llm_phase("api_http_fail")
        still_missing = sum(
            1 for i in candidates_idx if not (rows[i].get("ru") or "").strip()
        )
        return CatalogEnrichLLMOutcome(
            rows=rows,
            fallback_used=fb_used,
            candidates=len(candidates_idx),
            memory_cache_hits=mem_hits,
            redis_cache_hits=redis_hits,
            openai_batches_items=len(pending_batch),
            openai_ok=False if resp is None else resp.status_code < 400,
            truncated=truncated,
            still_missing=still_missing,
        )

    parsed: dict
    try:
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
        parsed_obj = json.loads(raw) if isinstance(raw, str) else {}
        if not isinstance(parsed_obj, dict):
            raise ValueError("not dict")
        parsed = parsed_obj
    except Exception:
        inc_catalog_enrich_llm_phase("api_parse_fail")
        still_missing = sum(
            1 for i in candidates_idx if not (rows[i].get("ru") or "").strip()
        )
        return CatalogEnrichLLMOutcome(
            rows=rows,
            fallback_used=fb_used,
            candidates=len(candidates_idx),
            memory_cache_hits=mem_hits,
            redis_cache_hits=redis_hits,
            openai_batches_items=len(pending_batch),
            openai_ok=False,
            truncated=truncated,
            still_missing=still_missing,
        )

    items = parsed.get("items")
    if not isinstance(items, list):
        inc_catalog_enrich_llm_phase("api_parse_fail")
        still_missing = sum(
            1 for i in candidates_idx if not (rows[i].get("ru") or "").strip()
        )
        return CatalogEnrichLLMOutcome(
            rows=rows,
            fallback_used=fb_used,
            candidates=len(candidates_idx),
            memory_cache_hits=mem_hits,
            redis_cache_hits=redis_hits,
            openai_batches_items=len(pending_batch),
            openai_ok=False,
            truncated=truncated,
            still_missing=still_missing,
        )

    by_idx: Dict[int, Dict[str, str]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            idx = int(it.get("i"))
        except (TypeError, ValueError):
            continue
        ru = str(it.get("ru") or "").strip()
        en = str(it.get("en") or "").strip()
        by_idx[idx] = {"ru": ru, "en": en}

    used_api = False
    for idx, tin, dom in pending_batch:
        hit = by_idx.get(idx)
        if not hit:
            continue
        ru, en = hit.get("ru", ""), hit.get("en", "")
        if not ru and not en:
            continue
        row = rows[idx]
        if ru:
            row["ru"] = ru
        if en:
            row["en"] = en
        row["source_ru"] = "openai_fallback"
        used_api = True
        if ru or en:
            _pair_cache_put(tin, dom, ru or "", en or row.get("en") or "")
            await _pair_redis_put(redis, redis_prefix, tin, dom, ru or "", en or row.get("en") or "", ttl)

    # HTTP OK но модель могла вернуть JSON без полезных ключей для части строк
    fb_used = fb_used or used_api or any(r.get("source_ru") == "openai_fallback" for r in rows)
    inc_catalog_enrich_llm_phase("api_applied" if used_api else "api_empty_response")

    still_missing = sum(1 for i in candidates_idx if not (rows[i].get("ru") or "").strip())
    openapi_ok_flag = resp is not None and resp.status_code < 400

    return CatalogEnrichLLMOutcome(
        rows=rows,
        fallback_used=bool(fb_used),
        candidates=len(candidates_idx),
        memory_cache_hits=mem_hits,
        redis_cache_hits=redis_hits,
        openai_batches_items=len(pending_batch),
        openai_ok=openapi_ok_flag,
        truncated=truncated,
        still_missing=still_missing,
    )
