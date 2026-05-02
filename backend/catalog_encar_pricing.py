"""Правила уровней цены Encar для каталога (долговременная переходная модель без полного hp_catalog).

Дорожки:
- full_customs  — есть данные для честной оценки с РФ таможней (правило зависит от типа топлива).
- korea_land_only — только Корея+логистика+комиссии, без сборов таможни РФ (сейчас: бензин/дизель с объёмом, но без л.с.).
- price_on_request — недостаточно данных (электро/гибрид без мощности, гибрид без объёма, ICE без объёма и т.д.).
"""

from __future__ import annotations

from typing import Any, Dict, Literal

EncarPricingTier = Literal["full_customs", "korea_land_only", "price_on_request"]

# Увеличивайте при изменении правил tier/калькулятора, чтобы repair и метрики отличали «старое».
PRICING_RULES_VERSION = "2026.05.05"


def parse_positive_int_cc(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            digits = "".join(ch for ch in value if ch.isdigit())
            if not digits:
                return None
            iv = int(digits)
        else:
            iv = int(float(value))
        return iv if iv > 0 else None
    except (TypeError, ValueError):
        return None


def encar_effective_payload_for_tier(data: Dict[str, Any]) -> Dict[str, Any]:
    """Поля для классификации tier: корень карточки + недостающее из spec_clean (как на фронте)."""
    if not isinstance(data, dict):
        return {}
    spec = data.get("spec_clean") if isinstance(data.get("spec_clean"), dict) else {}
    out = dict(data)
    if not (out.get("displacement") or out.get("displacement_cc") or out.get("engine_volume")):
        dcc = spec.get("displacement_cc")
        if dcc not in (None, ""):
            out["displacement_cc"] = dcc
    if not out.get("engine_type") and spec.get("engine_type"):
        out["engine_type"] = spec.get("engine_type")
    if (
        out.get("power") in (None, "")
        and out.get("power_hp") in (None, "")
        and out.get("outputHorsepower") in (None, "")
        and out.get("power_kw") in (None, "")
    ):
        sp = spec.get("power_hp")
        if sp not in (None, ""):
            out["power_hp"] = sp
    return out


def encar_tier_for_pricing_snapshot(data: Dict[str, Any]) -> EncarPricingTier:
    """Актуальный Encar-tier только по полям карточки (без учёта устаревшего pricing_clean).

    Вызывать для объявлений с уже проверенной ценой в листинге (см. encar_has_list_price).
    Не использовать для Dongchedi.
    """
    from market_pricing_shared import classify_fuel, parse_power_hp

    eff = encar_effective_payload_for_tier(data)
    fuel_kind = classify_fuel(eff)
    hp_raw = parse_power_hp(eff)
    hp_ok = isinstance(hp_raw, (int, float)) and float(hp_raw) > 0
    cc_val = parse_positive_int_cc(
        eff.get("displacement") or eff.get("displacement_cc") or eff.get("engine_volume")
    )
    cc_ok = cc_val is not None
    return encar_catalog_pricing_tier(fuel_kind=str(fuel_kind), hp_ok=hp_ok, cc_ok=cc_ok)


def encar_catalog_pricing_tier(*, fuel_kind: str, hp_ok: bool, cc_ok: bool) -> EncarPricingTier:
    fk = str(fuel_kind or "").strip().lower()
    if fk == "electric":
        return "full_customs" if hp_ok else "price_on_request"

    if fk == "hybrid":
        # Параллельный/последовательный в сыром Encar надёжно не различим без отдельных полей:
        # для «под ключ» требуем и суммарную мощность (из объявления), и объём ДВС там, где он есть в карточке.
        return "full_customs" if (hp_ok and cc_ok) else "price_on_request"

    # gas / diesel / lpg / hydrogen и пр. идут в ice
    if fk == "ice":
        if hp_ok and cc_ok:
            return "full_customs"
        if cc_ok and not hp_ok:
            return "korea_land_only"
        return "price_on_request"

    # неизвестный тип — безопасно «по запросу»
    return "price_on_request"


def sync_pricing_clean_block(data: dict) -> None:
    """Поддерживает pricing_clean финальными политиками после расчёта в postgres_catalog_sync."""
    if not isinstance(data, dict):
        return
    tier = data.get("pricing_tier")
    if tier not in ("full_customs", "korea_land_only", "price_on_request"):
        return
    mp = data.get("my_price")
    pc = data.get("pricing_clean")
    if not isinstance(pc, dict):
        pc = {}
        data["pricing_clean"] = pc
    pc["pricing_tier"] = tier
    pc["customs_included"] = tier == "full_customs"
    pc["price_on_request"] = tier == "price_on_request"
    pc["pricing_rules_version"] = PRICING_RULES_VERSION
    if tier == "price_on_request":
        pc.pop("final_price_rub", None)
        return
    if mp is not None:
        pc["final_price_rub"] = mp


def encar_json_suggests_pricing_resync(data: dict) -> bool:
    """Эвристика для repair: в JSON видно устаревший tier/версию правил при живой цене в листинге."""
    if not isinstance(data, dict):
        return False
    if str(data.get("source") or "").strip().lower() == "dongchedi":
        return False
    from catalog_listing_price import encar_has_list_price

    if not encar_has_list_price(data):
        return False
    pc = data.get("pricing_clean") if isinstance(data.get("pricing_clean"), dict) else {}
    if str(pc.get("pricing_rules_version") or "") != PRICING_RULES_VERSION:
        return True
    if pc.get("pricing_tier") != "price_on_request":
        return False
    return encar_tier_for_pricing_snapshot(data) != "price_on_request"

