"""
Обогащение «чистых» строк каталога (часто KO с Encar) → RU/EN без Postgres:
- fuel_label_aliases / facet fuel
- korea_static + china_static (в т.ч. кросс-доменный fallback)
- facet_canonical_english + романизация

Опционально: Postgres `term_translation_cache` только SELECT (батч в catalog_enrich_pg.py по флагам сервера+клиента).
Опциональное LLM — catalog_enrich_llm.py.

По умолчанию статика только, без БД и без OpenAI.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Literal, Tuple

from fastapi_app.facet_normalize import canon_catalog_fuel_ru
from localization.term_localizer import (
    _china_static_maps,
    _korea_static_maps,
    _lookup_china_static,
    _lookup_korea_static,
    _looks_english,
    _romanize_ko,
    detect_lang,
    facet_canonical_english,
)

_KNOWN_DOMAINS = frozenset(
    {
        "mark",
        "model",
        "generation",
        "configuration",
        "gradeName",
        "modelGroupName",
        "trim_name",
        "fuel",
        "fuel_type",
        "engine_type",
        "body_type",
        "color",
        "transmission_type",
        "drive_type",
        "prep_drive_type",
    }
)

_SourceRu = Literal[
    "empty",
    "fuel_facet",
    "korea_static_ru",
    "china_static_ru",
    "korea_cross_domain",
    "china_cross_domain",
    "openai_fallback",
    "postgres_term_cache",
    "none",
]

# Частые дубли в Encar между полями: ищем RU по соседним доменным словарям.
_CROSS_DOMAIN_FALLBACK_ORDER: Dict[str, Tuple[str, ...]] = {
    "generation": ("configuration", "gradeName", "trim_name", "modelGroupName"),
    "trim_name": ("configuration", "gradeName", "generation", "modelGroupName"),
    "gradeName": ("configuration", "trim_name", "generation"),
    "configuration": ("gradeName", "trim_name", "generation"),
    "modelGroupName": ("model", "generation", "trim_name"),
    "model": ("modelGroupName", "generation"),
    "drive_type": ("prep_drive_type",),
    "prep_drive_type": ("drive_type",),
}


def known_catalog_enrich_domains() -> frozenset[str]:
    return _KNOWN_DOMAINS


_WS_RE = re.compile(r"\s+")
_COMPACT_PUNCT = re.compile(r"[\s\-–—\(（\)）\[\]\"'`.,:·•]+")


def normalize_catalog_lookup_key(text: str) -> str:
    """NFKC, fullwidth space→space, схлопывание пробелов — для ключей статических словарей."""
    t = unicodedata.normalize("NFKC", (text or "").strip()).replace("\u3000", " ")
    return _WS_RE.sub(" ", t).strip()


def _canonical_domain_field(domain: str) -> str:
    raw = (domain or "").strip()
    low = raw.lower()
    if low == "fuel" or low == "fuel_type":
        return "engine_type"
    return raw


def canonical_catalog_enrich_domain(domain: str) -> str:
    """fuel|fuel_type → engine_type для внешних слоёв (PG cache, доменная логика)."""
    return _canonical_domain_field(domain)


def compact_catalog_lookup_variant(norm: str) -> str:
    """Второй шаг к статическим словарям: убираем пробелы/скобки/тире после NFKC (без fuzz по Левенштейну)."""
    n = (norm or "").strip()
    if not n:
        return ""
    c = _COMPACT_PUNCT.sub("", n)
    return c if len(c) >= 3 else ""


def _fuelish(domain: str) -> bool:
    low = domain.lower()
    return low in {"fuel", "fuel_type", "engine_type"}


def _lookup_ru_extended_primary(s_in: str, dom_eff: str) -> Tuple[str, _SourceRu]:
    """Прямой hit по dom_eff, затем кросс-домены (только статика). Один текстовый вариант."""
    korea_ru = _lookup_korea_static(_korea_static_maps(), s_in, "ru", dom_eff)
    if korea_ru:
        return korea_ru.strip(), "korea_static_ru"
    china_ru = _lookup_china_static(_china_static_maps(), s_in, "ru", dom_eff)
    if china_ru:
        return china_ru.strip(), "china_static_ru"
    for alt in _CROSS_DOMAIN_FALLBACK_ORDER.get(dom_eff, ()):
        k2 = _lookup_korea_static(_korea_static_maps(), s_in, "ru", alt)
        if k2:
            return k2.strip(), "korea_cross_domain"
        c2 = _lookup_china_static(_china_static_maps(), s_in, "ru", alt)
        if c2:
            return c2.strip(), "china_cross_domain"
    return "", "none"


def _lookup_ru_extended(s_in: str, dom_eff: str) -> Tuple[str, _SourceRu]:
    ru, sr = _lookup_ru_extended_primary(s_in, dom_eff)
    if ru:
        return ru, sr
    alt = compact_catalog_lookup_variant(s_in)
    if alt and alt != s_in:
        return _lookup_ru_extended_primary(alt, dom_eff)
    return "", "none"


def enrich_one(text: str, domain: str) -> Dict[str, Any]:
    text_in_disp = (text or "").strip()
    s_lookup = normalize_catalog_lookup_key(text)
    dom_eff = _canonical_domain_field(domain)

    if not text_in_disp:
        return {"text_in": text_in_disp, "domain": domain, "ru": "", "en": "", "source_ru": "empty"}

    if not s_lookup:
        return {"text_in": text_in_disp, "domain": domain, "ru": "", "en": "", "source_ru": "empty"}

    if _fuelish(domain):
        ru = canon_catalog_fuel_ru(s_lookup)
        if not ru:
            cq = compact_catalog_lookup_variant(s_lookup)
            if cq and cq != s_lookup:
                ru = canon_catalog_fuel_ru(cq)
        src_ru: _SourceRu = "fuel_facet" if ru else "none"
        en_hit = _lookup_korea_static(_korea_static_maps(), s_lookup, "en", "engine_type")
        china_en = (
            ""
            if en_hit
            else _lookup_china_static(_china_static_maps(), s_lookup, "en", "engine_type") or ""
        )
        en = (en_hit or china_en).strip()
        if not en and detect_lang(s_lookup) == "ko":
            en = _romanize_ko(s_lookup)
        elif not en and _looks_english(s_lookup):
            en = s_lookup.strip()
        return {"text_in": text_in_disp, "domain": domain, "ru": ru, "en": en, "source_ru": src_ru}

    ru, src_ru = _lookup_ru_extended(s_lookup, dom_eff)

    en = facet_canonical_english(s_lookup, dom_eff).strip()
    if not en and detect_lang(s_lookup) == "ko":
        en = _romanize_ko(s_lookup)
    elif not en and _looks_english(s_lookup):
        en = s_lookup.strip()

    return {"text_in": text_in_disp, "domain": domain, "ru": ru, "en": en, "source_ru": src_ru}


def enrich_batch(items: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    return [enrich_one(t, d) for t, d in items]
