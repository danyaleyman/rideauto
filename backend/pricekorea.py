#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расчёт стоимости по рынку Кореи (Encar): KRW, фрахт USD, брокер ₽, таможня РФ физлица.
Китай см. `pricechina.py`. Общие таблицы таможни и курсы — `market_pricing_shared`.
"""

from __future__ import annotations

import logging
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DOCUMENTS_KRW = 440_000
FREIGHT_USD = 1000
BROKER_RUB = 86_000


class PriceCalculatorKorea:
    """Калькулятор цен рынка Кореи (совместимость: прежний `PriceCalculator` для Encar)."""

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
            "documents_krw": DOCUMENTS_KRW,
            "freight_usd": FREIGHT_USD,
            "broker_rub": BROKER_RUB,
            "commission_rate": COMMISSION_RATE_DEFAULT,
            "commission_car_tiers": [],
            "excise_hp_tiers_rub_per_hp": [[hp, rate] for hp, rate in EXCISE_HP_TIERS_RUB_PER_HP],
        }
        base["commission_car_tiers"] = [[lim, amt] for lim, amt in COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB]
        pc = self._fx._price_cfg()
        base.update(pc)
        return base

    def _commission_schedule_loaded(self, cfg: Dict[str, Any]) -> List[Tuple[float, float]]:
        return parse_commission_schedule_from_config(cfg.get("commission_car_tiers"))

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

    def calculate_customs_fee(self, price_won: float, engine_volume: int) -> float:
        _ = price_won, engine_volume
        return 4924.0

    def calculate_duty(self, price_won: float, age_years: int) -> float:
        _ = price_won, age_years
        return 0.0

    def calculate_utilization_fee(self, engine_volume: int) -> float:
        from market_pricing_shared import UTIL_BASE_PERSONAL_RUB

        _ = engine_volume
        return UTIL_BASE_PERSONAL_RUB * 0.26

    def calculate_total_cost(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        fx = self._fx
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

        rub_pw, krw_pricing_source = fx.resolve_korea_krw_to_rub()
        amount_krw_with_docs = price_won + documents_krw
        car_and_docs_rub = amount_krw_with_docs * rub_pw
        documents_krw_rub = documents_krw * rub_pw

        usdt_rub = fx.get_cbr_usd_rub_exclusive()
        implied_kpw_usd = float(usdt_rub) / rub_pw if rub_pw > 1e-18 else fx.get_approx_krw_per_usd()

        cbr_usd_rub = fx.get_cbr_usd_rub_safe()
        freight_rub = freight_usd * cbr_usd_rub

        car_value_rub = car_and_docs_rub
        eur_rub = fx.get_cbr_eur_rub_safe()

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
        util = utilization_phys_person_rub(
            engine_cc=engine_cc,
            age_years=age,
            power_hp_ice=power_ice,
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
        vat = vat_import_rub(car_value_rub, duty, excise, fuel=fuel, age_years=age)

        customs_total = fee + duty + excise + util + vat

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
        fx = self._fx
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

        rub_pw, krw_pricing_source = fx.resolve_korea_krw_to_rub()
        amount_krw_with_docs = price_won + documents_krw
        car_and_docs_rub = amount_krw_with_docs * rub_pw
        documents_krw_rub = documents_krw * rub_pw

        usdt_rub = fx.get_cbr_usd_rub_exclusive()
        implied_kpw_usd = float(usdt_rub) / rub_pw if rub_pw > 1e-18 else fx.get_approx_krw_per_usd()

        cbr_usd_rub = fx.get_cbr_usd_rub_safe()
        freight_rub = freight_usd * cbr_usd_rub
        car_value_rub = car_and_docs_rub
        eur_rub = fx.get_cbr_eur_rub_safe()

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
