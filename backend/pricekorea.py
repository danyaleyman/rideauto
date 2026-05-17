#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расчёт стоимости по рынку Кореи (Encar): KRW, фрахт USD, брокер ₽, таможня РФ физлица.
Китай см. `pricechina.py`. Общие таблицы таможни и курсы — `market_pricing_shared`.
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

DOCUMENTS_KRW = 440_000
FREIGHT_USD = 1000
BROKER_RUB = 86_000
KOREA_PRICING_RULES_VERSION = "2026.05.17"


def sync_korea_pricing_clean_block(data: Dict[str, Any]) -> None:
    """Синхронизирует pricing_clean для карточек Кореи (Encar)."""
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
    pc["pricing_rules_version"] = KOREA_PRICING_RULES_VERSION
    if tier == "price_on_request":
        pc.pop("final_price_rub", None)
        return
    if mp is not None:
        pc["final_price_rub"] = mp


def korea_json_suggests_pricing_resync(data: Dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    if str(data.get("source") or "").strip().lower() != "encar":
        return False
    raw = data.get("price_won")
    has_price = False
    if raw is not None and raw != "":
        try:
            has_price = float(raw) > 0
        except (TypeError, ValueError):
            has_price = False
    if not has_price:
        return False
    pc = data.get("pricing_clean") if isinstance(data.get("pricing_clean"), dict) else {}
    return str(pc.get("pricing_rules_version") or "") != KOREA_PRICING_RULES_VERSION


class PriceCalculatorKorea:
    """Калькулятор цен рынка Кореи (совместимость: прежний `PriceCalculator` для Encar)."""

    def __init__(
        self,
        config_path: str = "config.json",
        *,
        fx: Optional[PricingFxRates] = None,
    ):
        self._fx = fx if fx is not None else PricingFxRates(config_path)
        self._fx_cache: Dict[str, Any] = {}
        self._fx_cache_at: float = 0.0

    def _get_price_config(self) -> Dict:
        base = {
            "cache_minutes": 5,
            "documents_krw": DOCUMENTS_KRW,
            "freight_usd": FREIGHT_USD,
            "broker_rub": BROKER_RUB,
            "commission_rate": COMMISSION_RATE_DEFAULT,
            "commission_car_tiers": [],
            "excise_hp_tiers_rub_per_hp": [[hp, rate] for hp, rate in EXCISE_HP_TIERS_RUB_PER_HP],
        }
        base["commission_car_tiers"] = [[lim, amt] for lim, amt in COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB]
        pc = self._fx._price_cfg()
        if isinstance(pc, dict):
            base.update(pc)
            kr = pc.get("korea")
            if isinstance(kr, dict):
                base.update(kr)
        return base

    def _commission_schedule_loaded(self, cfg: Dict[str, Any]) -> List[Tuple[float, float]]:
        return parse_commission_schedule_from_config(cfg.get("commission_car_tiers"))

    def _get_fx_rates_cached(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        ttl_sec = max(5.0, float(cfg.get("cache_minutes", 5) or 5) * 60.0)
        now = time.time()
        if self._fx_cache and (now - self._fx_cache_at) < ttl_sec:
            logger.debug(
                "Korea pricing FX cache hit: source=%s rub_pw=%.6f usd_rub=%.4f eur_rub=%.4f",
                self._fx_cache.get("krw_pricing_source"),
                float(self._fx_cache.get("rub_pw", 0.0) or 0.0),
                float(self._fx_cache.get("usdt_rub", 0.0) or 0.0),
                float(self._fx_cache.get("eur_rub", 0.0) or 0.0),
            )
            return dict(self._fx_cache)

        fx = self._fx
        fallback_rub_pw = float(self._fx_cache.get("rub_pw", 0.06) or 0.06)
        fallback_krw_source = str(self._fx_cache.get("krw_pricing_source", "fallback_last_known"))
        fallback_usd_rub = float(self._fx_cache.get("usdt_rub", 95.0) or 95.0)
        fallback_eur_rub = float(self._fx_cache.get("eur_rub", 105.0) or 105.0)

        try:
            rub_pw, krw_pricing_source = fx.resolve_korea_krw_to_rub()
            rub_pw = float(rub_pw)
            krw_pricing_source = str(krw_pricing_source or "unknown")
        except Exception as e:
            logger.warning("Korea pricing: KRW->RUB resolve failed, using fallback: %s", e)
            rub_pw = fallback_rub_pw
            krw_pricing_source = fallback_krw_source

        try:
            usdt_rub = float(fx.get_cbr_usd_rub_exclusive())
        except Exception as e:
            logger.warning("Korea pricing: USD/RUB fetch failed, using fallback: %s", e)
            usdt_rub = fallback_usd_rub

        try:
            eur_rub = float(fx.get_cbr_eur_rub_safe())
        except Exception as e:
            logger.warning("Korea pricing: EUR/RUB fetch failed, using fallback: %s", e)
            eur_rub = fallback_eur_rub

        implied_kpw_usd = float(usdt_rub) / rub_pw if rub_pw > 1e-18 else float(fx.get_approx_krw_per_usd())
        payload = {
            "rub_pw": rub_pw,
            "krw_pricing_source": krw_pricing_source,
            "usdt_rub": usdt_rub,
            "eur_rub": eur_rub,
            "implied_kpw_usd": implied_kpw_usd,
        }
        logger.debug(
            "Korea pricing FX refresh: source=%s rub_pw=%.6f usd_rub=%.4f eur_rub=%.4f implied_krw_per_usd=%.2f",
            krw_pricing_source,
            rub_pw,
            usdt_rub,
            eur_rub,
            implied_kpw_usd,
        )
        self._fx_cache = dict(payload)
        self._fx_cache_at = now
        return payload

    def get_krw_usdt_rate(self) -> float:
        return self._fx.get_krw_usdt_rate()

    def get_usdt_rub_rate(self) -> float:
        return self._fx.get_usdt_rub_rate()

    def get_cbr_eur_rub_safe(self) -> float:
        return self._fx.get_cbr_eur_rub_safe()

    def get_cbr_usd_rub_safe(self) -> float:
        return self._fx.get_cbr_usd_rub_safe()

    def get_cbr_krw_rub_per_won_optional(self) -> Optional[float]:
        return self._fx.get_cbr_krw_rub_per_won_optional()

    def calculate_customs_fee_tiered(self, car_value_rub: float) -> float:
        return customs_fee(car_value_rub)

    def calculate_total_cost(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        cfg = self._get_price_config()
        documents_krw = float(cfg.get("documents_krw", DOCUMENTS_KRW))
        freight_usd = float(cfg.get("freight_usd", FREIGHT_USD))
        broker_rub = float(cfg.get("broker_rub", BROKER_RUB))
        sched = self._commission_schedule_loaded(cfg)

        price_won_10k = car_data.get("price_won")
        if price_won_10k is None and "price" in car_data:
            try:
                p = car_data["price"]
                price_won_10k = int(p) if isinstance(p, (int, float)) else int(str(p).replace(" ", ""))
            except (TypeError, ValueError):
                price_won_10k = 0
        if price_won_10k is None:
            price_won_10k = 0
        price_won = float(price_won_10k) * 10000.0

        fx_rates = self._get_fx_rates_cached(cfg)
        rub_pw = float(fx_rates["rub_pw"])
        krw_pricing_source = str(fx_rates["krw_pricing_source"])
        amount_krw_with_docs = price_won + documents_krw
        car_and_docs_rub = amount_krw_with_docs * rub_pw
        documents_krw_rub = documents_krw * rub_pw

        usdt_rub = float(fx_rates["usdt_rub"])
        implied_kpw_usd = float(fx_rates["implied_kpw_usd"])
        cbr_usd_rub = usdt_rub
        freight_rub = freight_usd * usdt_rub

        car_value_rub = car_and_docs_rub
        eur_rub = float(fx_rates["eur_rub"])

        fuel = classify_fuel(car_data)
        engine_cc, power_ice = ice_engine_inputs(car_data, fuel)
        year = parse_year(car_data)
        age = age_years_car(year)

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

        comm, comm_eff = commission_rub_tiered(car_value_rub, customs_total, broker_rub, sched)
        vehicle_sum = car_value_rub + freight_rub + customs_total
        total_with_commission = vehicle_sum + broker_rub + comm

        return {
            "price_won": price_won,
            "price_rub": car_value_rub,
            "documents_krw_rub": documents_krw_rub,
            "freight_rub": freight_rub,
            "customs_fee": fee,
            "duty": duty,
            "excise": excise,
            "utilization": util,
            "vat": vat,
            "customs_total": customs_total,
            "broker_rub": broker_rub,
            "commission": comm,
            "commission_rate_effective": comm_eff,
            "commission_rate_default": float(COMMISSION_RATE_DEFAULT),
            "vehicle_sum": vehicle_sum,
            "total_with_commission": total_with_commission,
            "krw_per_usdt": implied_kpw_usd,
            "usdt_rub": usdt_rub,
            "eur_rub": eur_rub,
            "cbr_usd_rub": cbr_usd_rub,
            "cbr_krw_rub_per_won": float(rub_pw),
            "krw_pricing_source": krw_pricing_source,
        }

    def calculate_total_cost_excluding_rf_customs(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        cfg = self._get_price_config()
        documents_krw = float(cfg.get("documents_krw", DOCUMENTS_KRW))
        freight_usd = float(cfg.get("freight_usd", FREIGHT_USD))
        broker_rub = float(cfg.get("broker_rub", BROKER_RUB))
        sched = self._commission_schedule_loaded(cfg)

        price_won_10k = car_data.get("price_won")
        if price_won_10k is None and "price" in car_data:
            try:
                p = car_data["price"]
                price_won_10k = int(p) if isinstance(p, (int, float)) else int(str(p).replace(" ", ""))
            except (TypeError, ValueError):
                price_won_10k = 0
        if price_won_10k is None:
            price_won_10k = 0
        price_won = float(price_won_10k) * 10000.0

        fx_rates = self._get_fx_rates_cached(cfg)
        rub_pw = float(fx_rates["rub_pw"])
        krw_pricing_source = str(fx_rates["krw_pricing_source"])
        amount_krw_with_docs = price_won + documents_krw
        car_and_docs_rub = amount_krw_with_docs * rub_pw
        documents_krw_rub = documents_krw * rub_pw

        usdt_rub = float(fx_rates["usdt_rub"])
        implied_kpw_usd = float(fx_rates["implied_kpw_usd"])

        cbr_usd_rub = usdt_rub
        freight_rub = freight_usd * cbr_usd_rub
        car_value_rub = car_and_docs_rub
        eur_rub = float(fx_rates["eur_rub"])

        fee = duty = excise = util = vat = 0.0
        customs_total = 0.0
        comm, comm_eff = commission_rub_tiered(car_and_docs_rub, customs_total, broker_rub, sched)
        vehicle_sum = car_and_docs_rub + freight_rub
        total_with_commission = vehicle_sum + broker_rub + comm

        return {
            "price_won": price_won,
            "price_rub": car_value_rub,
            "documents_krw_rub": documents_krw_rub,
            "freight_rub": freight_rub,
            "customs_fee": fee,
            "duty": duty,
            "excise": excise,
            "utilization": util,
            "vat": vat,
            "customs_total": customs_total,
            "broker_rub": broker_rub,
            "commission": comm,
            "commission_rate_effective": comm_eff,
            "commission_rate_default": float(COMMISSION_RATE_DEFAULT),
            "vehicle_sum": vehicle_sum,
            "total_with_commission": total_with_commission,
            "krw_per_usdt": implied_kpw_usd,
            "usdt_rub": usdt_rub,
            "eur_rub": eur_rub,
            "cbr_usd_rub": cbr_usd_rub,
            "cbr_krw_rub_per_won": float(rub_pw),
            "krw_pricing_source": krw_pricing_source,
        }

    def update_car_with_prices(self, car_data: Dict[str, Any]) -> Dict[str, Any]:
        prices = self.calculate_total_cost(car_data)
        car_data["price_rub_estimate"] = prices["price_rub"]
        car_data["documents_krw_rub"] = prices.get("documents_krw_rub", 0)
        car_data["freight_rub"] = prices["freight_rub"]
        car_data["customs_fee_rub"] = prices["customs_fee"]
        car_data["duty_rub"] = prices["duty"]
        car_data["excise_rub"] = prices["excise"]
        car_data["util_rub"] = prices["utilization"]
        car_data["vat_rub"] = prices["vat"]
        car_data["customs_total_rub"] = prices["customs_total"]
        car_data["broker_rub"] = prices["broker_rub"]
        car_data["commission_rub"] = prices["commission"]
        car_data["vehicle_sum_rub"] = prices["vehicle_sum"]
        car_data["my_price"] = prices["total_with_commission"]
        car_data["krw_per_usdt"] = prices.get("krw_per_usdt")
        car_data["usdt_rub"] = prices.get("usdt_rub")
        car_data["commission_rate_effective"] = prices.get("commission_rate_effective")
        car_data["commission_rate_default"] = prices.get("commission_rate_default")
        sync_korea_pricing_clean_block(car_data)
        return car_data

    def update_car_with_prices_land_only(self, car_data: Dict[str, Any]) -> Dict[str, Any]:
        prices = self.calculate_total_cost_excluding_rf_customs(car_data)
        car_data["price_rub_estimate"] = prices["price_rub"]
        car_data["documents_krw_rub"] = prices.get("documents_krw_rub", 0)
        car_data["freight_rub"] = prices["freight_rub"]
        car_data["customs_fee_rub"] = prices["customs_fee"]
        car_data["duty_rub"] = prices["duty"]
        car_data["excise_rub"] = prices["excise"]
        car_data["util_rub"] = prices["utilization"]
        car_data["vat_rub"] = prices["vat"]
        car_data["customs_total_rub"] = prices["customs_total"]
        car_data["broker_rub"] = prices["broker_rub"]
        car_data["commission_rub"] = prices["commission"]
        car_data["vehicle_sum_rub"] = prices["vehicle_sum"]
        car_data["my_price"] = prices["total_with_commission"]
        car_data["krw_per_usdt"] = prices.get("krw_per_usdt")
        car_data["usdt_rub"] = prices.get("usdt_rub")
        car_data["commission_rate_effective"] = prices.get("commission_rate_effective")
        car_data["commission_rate_default"] = prices.get("commission_rate_default")
        sync_korea_pricing_clean_block(car_data)
        return car_data


# Обратная совместимость имён
PriceCalculator = PriceCalculatorKorea


def main() -> None:
    calculator = PriceCalculatorKorea()
    test_car = {
        "price_won": 3000,
        "displacement": 2000,
        "year": 2019,
        "engine_type": "가솔린",
        "power": "184",
    }
    p = calculator.calculate_total_cost(test_car)
    print("Пример расчёта (Корея):")
    for k in (
        "price_won",
        "price_rub",
        "documents_krw_rub",
        "freight_rub",
        "customs_fee",
        "duty",
        "excise",
        "utilization",
        "vat",
        "customs_total",
        "broker_rub",
        "commission",
        "total_with_commission",
    ):
        v = p.get(k)
        if isinstance(v, float):
            print(f"  {k}: {v:,.2f}")
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
