"""
Опциональное дополнение enrich-ответа через OpenAI-совместимый Chat API — без Postgres, только HTTP.
Кэш в памяти процесса (LRU): повторые пары text+domain не бьют сеть.

Ключ из env уже используется в Settings.translate_api_key (OPENAI_API_KEY / WRA_TRANSLATE_API_KEY).
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import httpx

from fastapi_app.config import Settings

_PAIR_CACHE_MAX = 512
_PAIR_CACHE: OrderedDict[str, Tuple[str, str]] = OrderedDict()


def _cache_key(text: str, domain: str) -> str:
    return hashlib.sha256(f"{domain}\n{text}".encode("utf-8")).hexdigest()


def _pair_cache_get(text: str, domain: str) -> Optional[Tuple[str, str]]:
    k = _cache_key(text, domain)
    v = _PAIR_CACHE.get(k)
    if v is None:
        return None
    _PAIR_CACHE.move_to_end(k)
    return v


def _pair_cache_put(text: str, domain: str, ru: str, en: str) -> None:
    k = _cache_key(text, domain)
    _PAIR_CACHE[k] = (ru.strip(), en.strip())
    _PAIR_CACHE.move_to_end(k)
    while len(_PAIR_CACHE) > _PAIR_CACHE_MAX:
        _PAIR_CACHE.popitem(last=False)


def _chat_url(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        return ""
    if b.endswith("/chat/completions"):
        return b
    return f"{b}/chat/completions"


async def openai_enrich_missing(
    rows: List[Dict[str, Any]],
    *,
    settings: Settings,
    max_llm_items: int,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Для строк с пустым `ru` и KO/ZH текстом — пробуем один batched запрос."""
    from localization.term_localizer import detect_lang

    if not settings.catalog_enrich_llm_fallback:
        return rows, False
    api_key = (settings.translate_api_key or "").strip()
    if not api_key:
        return rows, False

    pending: List[Tuple[int, str, str]] = []
    for i, row in enumerate(rows):
        tin = (row.get("text_in") or "").strip()
        dom = (row.get("domain") or "").strip()
        ru = (row.get("ru") or "").strip()
        if not tin or ru:
            continue
        lang = detect_lang(tin)
        if lang not in ("ko", "zh"):
            continue
        ck = _pair_cache_get(tin, dom)
        if ck:
            rr, ee = ck
            row["ru"] = rr
            if ee:
                row["en"] = ee
            row["source_ru"] = "openai_fallback"
            continue
        pending.append((i, tin, dom))
        if len(pending) >= max_llm_items:
            break

    if not pending:
        out_any = any(r.get("source_ru") == "openai_fallback" for r in rows)
        return rows, out_any

    payload_items = [{"i": a[0], "text": a[1], "domain": a[2]} for a in pending]
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
        return rows, False

    model = (settings.catalog_enrich_openai_model or settings.translate_openai_model or "gpt-4o-mini").strip()
    req_body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "You reply with compact JSON only. Keys in English.",
            },
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=min(45.0, settings.translate_timeout_sec + 15), trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=req_body)
    except Exception:
        return rows, False

    if resp.status_code >= 400:
        return rows, False

    try:
        data = resp.json()
        raw = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        return rows, False

    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return rows, False

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

    used = False
    for idx, tin, dom in pending:
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
        used = True
        if ru or en:
            _pair_cache_put(tin, dom, ru or "", en or row.get("en") or "")

    return rows, used
