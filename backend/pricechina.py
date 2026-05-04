#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расчёт стоимости по рынку Китая (Dongchendi и др.): юань → ₽ ЦБ, доставка документов ¥,
таможня РФ физлица. Корея — только `pricekorea.py`; общее — `market_pricing_shared`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from market_pricing_shared import (
    COMMISSION_RATE_DEFAULT,
    COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB,
    EXCISE_HP_TIERS_RUB_PER_HP,
    PricingFxRates,
    age_years_car,
    classify_fuel,
    commission_rub_tiered,
    customs_fee,
    duty_phys_person_rub,
    excise_rub,
    ice_engine_inputs,
    parse_commission_schedule_from_config,
    parse_power_hp,
    parse_year,
    utilization_phys_person_rub,
    vat_import_rub,
)

CHINA_DOCS_DELIVERY_CNY = 13_500
CHINA_BROKER_RUB = 86_100

# Банк ВТБ: комиссия за перевод в ₽, 2% от стоимости авто (закуп в юанях × курс ЦБ).
VTB_BANK_TRANSFER_RATE = 0.02

# Bump при изменении формул/констант China-калькулятора (метрики каталога, repair).
CHINA_PRICING_RULES_VERSION = "2026.05.03"


def sync_china_pricing_clean_block(data: Dict[str, Any]) -> None:
    """Обновляет `pricing_clean` для карточек China (che168) после расчёта или skip."""
    if not isinstance(data, dict):
        return
    tier = data.get("pricing_tier")
    if tier not in ("full_customs", "price_on_request"):
        tier = "price_on_request" if data.get("price_on_request") else "full_customs"
        data["pricing_tier"] = tier
    mp = data.get("my_price")
    pc = data.get("pricing_clean")
    if not isinstance(pc, dict):
        pc = {}
        data["pricing_clean"] = pc
    pc["pricing_tier"] = tier
    pc["customs_included"] = tier == "full_customs"
    pc["price_on_request"] = tier == "price_on_request"
    pc["pricing_rules_version"] = CHINA_PRICING_RULES_VERSION
    if tier == "price_on_request":
        pc.pop("final_price_rub", None)
        return
    if mp is not None:
        pc["final_price_rub"] = mp


def china_json_suggests_pricing_resync(data: Dict[str, Any]) -> bool:
    """Устаревший блок цен China в JSON при наличии исходной цены в ¥ — нужен пересчёт каталога."""
    if not isinstance(data, dict):
        return False
    if str(data.get("source") or "").strip().lower() != "che168":
        return False
    from catalog_listing_price import china_has_source_price

    if not china_has_source_price(data):
        return False
    pc = data.get("pricing_clean") if isinstance(data.get("pricing_clean"), dict) else {}
    return str(pc.get("pricing_rules_version") or "") != CHINA_PRICING_RULES_VERSION


def parse_price_cny(car_data: Dict[str, Any]) -> float:
    raw = car_data.get("price_cny")
    if raw is None or raw == "":
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw) if float(raw) > 0 else 0.0
    s = str(raw).strip().replace(" ", "").replace(",", "")
    if not s:
        return 0.0
    try:
        v = float(s)
        return v if v > 0 else 0.0
    except ValueError:
        return 0.0


class PriceCalculatorChina:
    def __init__(
        self,
        config_path: str = "config.json",
        *,
        fx: Optional[PricingFxRates] = None,
    ):
        self._fx = fx if fx is not None else PricingFxRates(config_path)

    def _get_price_config(self) -> Dict:
        base = {
            "cache_minutes": 5,
            "china_docs_delivery_cny": CHINA_DOCS_DELIVERY_CNY,
            "china_broker_rub": CHINA_BROKER_RUB,
            "commission_rate": COMMISSION_RATE_DEFAULT,
            "commission_car_tiers": [[lim, amt] for lim, amt in COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB],
            "excise_hp_tiers_rub_per_hp": [[hp, rate] for hp, rate in EXCISE_HP_TIERS_RUB_PER_HP],
        }
        pc = self._fx._price_cfg()
        base.update(pc)
        return base

    def _commission_schedule_loaded(self, cfg: Dict[str, Any]) -> List[Tuple[float, float]]:
        return parse_commission_schedule_from_config(cfg.get("commission_car_tiers"))

    def calculate_total_cost_china(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        fx = self._fx
        cfg = self._get_price_config()
        docs_delivery_cny = float(cfg.get("china_docs_delivery_cny", CHINA_DOCS_DELIVERY_CNY))
        broker_rub = float(cfg.get("china_broker_rub", CHINA_BROKER_RUB))
        sched = self._commission_schedule_loaded(cfg)

        price_cny = parse_price_cny(car_data)
        if price_cny <= 0:
            raise ValueError("price_cny is missing or non-positive")

        cny_rub = fx.get_cbr_cny_rub_safe()
        eur_rub = fx.get_cbr_eur_rub_safe()
        car_value_rub = price_cny * cny_rub
        docs_delivery_rub = docs_delivery_cny * cny_rub

        fuel = classify_fuel(car_data)
        engine_cc, power_ice = ice_engine_inputs(car_data, fuel)
        year = parse_year(car_data)
        age = age_years_car(year)

        fee = customs_fee(car_value_rub)
        duty = duty_phys_person_rub(
            car_value_rub=car_value_rub,
            eur_rub=eur_rub,
            engine_cc=engine_cc,
            age_years=age,
            fuel=fuel,
        )
        excise_tiers_cfg = cfg.get("excise_hp_tiers_rub_per_hp")
        excise_tiers: Optional[List[Tuple[float, float]]] = None
        if isinstance(excise_tiers_cfg, list):
            parsed: List[Tuple[float, float]] = []
            for item in excise_tiers_cfg:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    continue
                try:
                    parsed.append((float(item[0]), float(item[1])))
                except (TypeError, ValueError):
                    continue
            if parsed:
                excise_tiers = sorted(parsed, key=lambda x: x[0])
        power_for_excise = parse_power_hp(car_data)
        if power_for_excise is None:
            power_for_excise = power_ice
        if fuel == "electric":
            excise = 0.0
        else:
            excise = excise_rub(power_for_excise, excise_tiers)
        util = utilization_phys_person_rub(
            engine_cc=engine_cc,
            age_years=age,
            power_hp_ice=power_ice,
            fuel=fuel,
            car_data=car_data,
        )
        vat = vat_import_rub(car_value_rub, duty, excise, fuel=fuel, age_years=age)
        customs_total = fee + duty + excise + util + vat

        vtb_bank_transfer_rub = car_value_rub * VTB_BANK_TRANSFER_RATE
        vehicle_sum = (
            car_value_rub + docs_delivery_rub + customs_total + broker_rub + vtb_bank_transfer_rub
        )
        commission, comm_eff = commission_rub_tiered(car_value_rub, customs_total, broker_rub, sched)
        total_with_commission = vehicle_sum + commission

        return {
            "price_cny": price_cny,
            "price_rub": car_value_rub,
            "china_docs_delivery_cny": docs_delivery_cny,
            "china_docs_delivery_rub": docs_delivery_rub,
            "vtb_bank_transfer_rub": vtb_bank_transfer_rub,
            "customs_fee": fee,
            "duty": duty,
            "excise": excise,
            "utilization": util,
            "vat": vat,
            "customs_total": customs_total,
            "broker_rub": broker_rub,
            "commission": commission,
            "commission_rate_effective": comm_eff,
            "commission_rate_default": float(COMMISSION_RATE_DEFAULT),
            "vehicle_sum": vehicle_sum,
            "total_with_commission": total_with_commission,
            "cny_rub": cny_rub,
            "eur_rub": eur_rub,
        }

    def update_china_car_with_prices(self, car_data: Dict[str, Any]) -> Dict[str, Any]:
        prices = self.calculate_total_cost_china(car_data)
        car_data["price_rub_estimate"] = prices["price_rub"]
        car_data["china_docs_delivery_cny"] = prices["china_docs_delivery_cny"]
        car_data["china_docs_delivery_rub"] = prices["china_docs_delivery_rub"]
        car_data["customs_fee_rub"] = prices["customs_fee"]
        car_data["duty_rub"] = prices["duty"]
        car_data["excise_rub"] = prices["excise"]
        car_data["util_rub"] = prices["utilization"]
        car_data["vat_rub"] = prices["vat"]
        car_data["customs_total_rub"] = prices["customs_total"]
        car_data["broker_rub"] = prices["broker_rub"]
        car_data["commission_rub"] = prices["commission"]
        car_data["vtb_bank_transfer_rub"] = prices["vtb_bank_transfer_rub"]
        car_data["vehicle_sum_rub"] = prices["vehicle_sum"]
        car_data["my_price"] = prices["total_with_commission"]
        car_data["cny_rub"] = prices.get("cny_rub")
        car_data["commission_rate_effective"] = prices.get("commission_rate_effective")
        car_data["commission_rate_default"] = prices.get("commission_rate_default")
        return car_data
