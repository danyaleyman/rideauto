"""
Обогащение «чистых» строк каталога (часто KO с Encar) → RU/EN без Postgres:
- fuel_label_aliases / facet fuel
- korea_static + china_static (в т.ч. кросс-доменный fallback)
- facet_canonical_english + романизация

Опциональное LLM-дозаполнение (только по флагу в Settings + поле запроса): см. catalog_enrich_llm.py.
Без term_translation_cache и без нагрузки на БД в основной ветке.
"""
from __future__ import annotations

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


def _canonical_domain_field(domain: str) -> str:
    raw = (domain or "").strip()
    low = raw.lower()
    if low == "fuel" or low == "fuel_type":
        return "engine_type"
    return raw


def _fuelish(domain: str) -> bool:
    low = domain.lower()
    return low in {"fuel", "fuel_type", "engine_type"}


def _lookup_ru_extended(s_in: str, dom_eff: str) -> Tuple[str, _SourceRu]:
    """Прямой hit по dom_eff, затем кросс-домены (только статика)."""
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


def enrich_one(text: str, domain: str) -> Dict[str, Any]:
    s_in = (text or "").strip()
    dom_eff = _canonical_domain_field(domain)

    if not s_in:
        return {"text_in": s_in, "domain": domain, "ru": "", "en": "", "source_ru": "empty"}

    if _fuelish(domain):
        ru = canon_catalog_fuel_ru(s_in)
        src_ru: _SourceRu = "fuel_facet" if ru else "none"
        en_hit = _lookup_korea_static(_korea_static_maps(), s_in, "en", "engine_type")
        china_en = (
            ""
            if en_hit
            else _lookup_china_static(_china_static_maps(), s_in, "en", "engine_type") or ""
        )
        en = (en_hit or china_en).strip()
        if not en and detect_lang(s_in) == "ko":
            en = _romanize_ko(s_in)
        elif not en and _looks_english(s_in):
            en = s_in.strip()
        return {"text_in": s_in, "domain": domain, "ru": ru, "en": en, "source_ru": src_ru}

    ru, src_ru = _lookup_ru_extended(s_in, dom_eff)

    en = facet_canonical_english(s_in, dom_eff).strip()
    if not en and detect_lang(s_in) == "ko":
        en = _romanize_ko(s_in)
    elif not en and _looks_english(s_in):
        en = s_in.strip()

    return {"text_in": s_in, "domain": domain, "ru": ru, "en": en, "source_ru": src_ru}


def enrich_batch(items: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    return [enrich_one(t, d) for t, d in items]
