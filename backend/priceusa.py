#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расчёт стоимости по рынку США (Autotrader): USD лота → ₽, фрахт, брокер, таможня РФ физлица.
Корея — pricekorea.py, Китай — pricechina.py. Курсы — market_pricing_shared.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from market_pricing_shared import (
    COMMISSION_RATE_DEFAULT,
    COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB,
    EXCISE_HP_TIERS_RUB_PER_HP,
    PricingFxRates,
    age_years_car,
    classify_fuel,
    commission_rub_tiered,
    ice_engine_inputs,
    parse_commission_schedule_from_config,
    parse_year,
    phys_person_import_charges,
)

logger = logging.getLogger(__name__)

USA_PRICING_RULES_VERSION = "2026.10.06"
FREIGHT_USD_DEFAULT = 1500.0
BROKER_RUB_DEFAULT = 86_000.0
BANK_TRANSFER_RATE = 0.01  # ~1% на перевод USD


def parse_price_usd(car_data: Dict[str, Any]) -> float:
    raw = car_data.get("price_usd")
    if raw is not None and raw != "":
        try:
            v = float(raw)
            return v if v > 0 else 0.0
        except (TypeError, ValueError):
            pass
    pd = car_data.get("pricingDetail")
    if isinstance(pd, dict):
        for key in ("salePrice", "preFeeDerivedPrice", "msrp", "displayPrice"):
            try:
                v = float(pd.get(key))
                if v > 0:
                    return v
            except (TypeError, ValueError):
                continue
    return 0.0


def age_years_for_customs(car_data: Dict[str, Any]) -> int:
    y = parse_year(car_data)
    if y is None:
        return 5
    return int(age_years_car(y))


def sync_usa_pricing_clean_block(data: Dict[str, Any]) -> None:
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
    pc["pricing_rules_version"] = USA_PRICING_RULES_VERSION
    if tier == "price_on_request":
        pc.pop("final_price_rub", None)
        return
    if mp is not None:
        pc["final_price_rub"] = mp


def usa_json_suggests_pricing_resync(data: Dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    if str(data.get("source") or "").strip().lower() not in ("autotrader", "usa"):
        return False
    if parse_price_usd(data) <= 0:
        return False
    pc = data.get("pricing_clean") if isinstance(data.get("pricing_clean"), dict) else {}
    return str(pc.get("pricing_rules_version") or "") != USA_PRICING_RULES_VERSION


class PriceCalculatorUsa:
    def __init__(
        self,
        config_path: str = "config.json",
        *,
        fx: Optional[PricingFxRates] = None,
    ):
        self._fx = fx if fx is not None else PricingFxRates(config_path)
        self._fx_cache: Dict[str, float] = {}
        self._fx_cache_at: float = 0.0

    def _get_price_config(self) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "cache_minutes": 5,
            "freight_usd": FREIGHT_USD_DEFAULT,
            "broker_rub": BROKER_RUB_DEFAULT,
            "bank_transfer_rate": BANK_TRANSFER_RATE,
            "commission_rate": COMMISSION_RATE_DEFAULT,
            "commission_car_tiers": [[lim, amt] for lim, amt in COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB],
            "excise_hp_tiers_rub_per_hp": [[hp, rate] for hp, rate in EXCISE_HP_TIERS_RUB_PER_HP],
        }
        pc = self._fx._price_cfg()
        if isinstance(pc, dict):
            base.update(pc)
            usa_cfg = pc.get("usa")
            if isinstance(usa_cfg, dict):
                base.update(usa_cfg)
        return base

    def _get_fx_rates_cached(self, cfg: Dict[str, Any]) -> Tuple[float, float]:
        ttl_sec = max(5.0, float(cfg.get("cache_minutes", 5) or 5) * 60.0)
        now = time.time()
        if self._fx_cache and (now - self._fx_cache_at) < ttl_sec:
            return float(self._fx_cache["usd_rub"]), float(self._fx_cache["eur_rub"])
        try:
            usd_rub = float(self._fx.get_cbr_usd_rub_exclusive())
            eur_rub = float(self._fx.get_cbr_eur_rub_safe())
        except Exception as e:
            logger.warning("USA pricing: FX fetch failed, fallback: %s", e)
            usd_rub = float(self._fx_cache.get("usd_rub", 95.0) or 95.0)
            eur_rub = float(self._fx_cache.get("eur_rub", 105.0) or 105.0)
        self._fx_cache = {"usd_rub": usd_rub, "eur_rub": eur_rub}
        self._fx_cache_at = now
        return usd_rub, eur_rub

    def calculate_total_cost_usa(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        cfg = self._get_price_config()
        freight_usd = float(cfg.get("freight_usd", FREIGHT_USD_DEFAULT))
        broker_rub = float(cfg.get("broker_rub", BROKER_RUB_DEFAULT))
        bank_rate = float(cfg.get("bank_transfer_rate", BANK_TRANSFER_RATE))
        sched = parse_commission_schedule_from_config(cfg.get("commission_car_tiers"))

        price_usd = parse_price_usd(car_data)
        if price_usd <= 0:
            raise ValueError("price_usd is missing or non-positive")

        usd_rub, eur_rub = self._get_fx_rates_cached(cfg)
        car_value_rub = price_usd * usd_rub
        freight_rub = freight_usd * usd_rub
        bank_transfer_rub = car_value_rub * bank_rate

        fuel = classify_fuel(car_data)
        engine_cc, _power = ice_engine_inputs(car_data, fuel)
        age = age_years_for_customs(car_data)

        customs = phys_person_import_charges(
            car_value_rub=car_value_rub,
            eur_rub=eur_rub,
            engine_cc=engine_cc,
            age_years=age,
            fuel=fuel,
            car_data=car_data,
            excise_hp_tiers=cfg.get("excise_hp_tiers_rub_per_hp"),
        )
        fee = customs["customs_fee"]
        duty = customs["duty"]
        excise = customs["excise"]
        util = customs["utilization"]
        vat = customs["vat"]
        customs_total = customs["customs_total"]

        vehicle_sum = car_value_rub + freight_rub + customs_total + broker_rub + bank_transfer_rub
        commission, comm_eff = commission_rub_tiered(car_value_rub, customs_total, broker_rub, sched)
        total_with_commission = vehicle_sum + commission

        return {
            "price_usd": price_usd,
            "price_rub": car_value_rub,
            "freight_usd": freight_usd,
            "freight_rub": freight_rub,
            "bank_transfer_rub": bank_transfer_rub,
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
            "usd_rub": usd_rub,
            "eur_rub": eur_rub,
        }

    def update_usa_car_with_prices(self, car_data: Dict[str, Any]) -> Dict[str, Any]:
        prices = self.calculate_total_cost_usa(car_data)
        car_data["price_rub_estimate"] = prices["price_rub"]
        car_data["freight_usd"] = prices["freight_usd"]
        car_data["freight_rub"] = prices["freight_rub"]
        car_data["customs_fee_rub"] = prices["customs_fee"]
        car_data["duty_rub"] = prices["duty"]
        car_data["excise_rub"] = prices["excise"]
        car_data["util_rub"] = prices["utilization"]
        car_data["vat_rub"] = prices["vat"]
        car_data["customs_total_rub"] = prices["customs_total"]
        car_data["broker_rub"] = prices["broker_rub"]
        car_data["commission_rub"] = prices["commission"]
        car_data["vtb_bank_transfer_rub"] = prices["bank_transfer_rub"]
        car_data["vehicle_sum_rub"] = prices["vehicle_sum"]
        car_data["my_price"] = prices["total_with_commission"]
        car_data["usdt_rub"] = prices.get("usd_rub")
        car_data["usd_rub"] = prices.get("usd_rub")
        car_data["commission_rate_effective"] = prices.get("commission_rate_effective")
        car_data["commission_rate_default"] = prices.get("commission_rate_default")
        car_data["price_on_request"] = False
        car_data["pricing_tier"] = "full_customs"
        return car_data
