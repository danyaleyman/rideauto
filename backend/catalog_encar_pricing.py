"""Правила уровней цены Encar для каталога (долговременная переходная модель без полного hp_catalog).

Дорожки:
- full_customs  — есть данные для честной оценки с РФ таможней (правило зависит от типа топлива).
- korea_land_only — только Корея+логистика+комиссии, без сборов таможни РФ (сейчас: бензин/дизель с объёмом, но без л.с.).
- price_on_request — недостаточно данных (электро/гибрид без мощности, гибрид без объёма, ICE без объёма и т.д.).
"""

from __future__ import annotations

from typing import Literal

EncarPricingTier = Literal["full_customs", "korea_land_only", "price_on_request"]


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
    if tier == "price_on_request":
        pc.pop("final_price_rub", None)
        return
    if mp is not None:
        pc["final_price_rub"] = mp

