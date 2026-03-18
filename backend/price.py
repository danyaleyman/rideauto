#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расчет стоимости автомобиля:
- Стоимость авто из выгрузки (KRW).
- Конвертация по крипте: KRW → USDT, USDT → RUB.
- Фиксированные платежи в крипте: 440 000 KRW (документы Корея), 1000 $ (фрахт).
- Растаможка по курсам ЦБ и постановлениям (таможенный сбор, пошлина, утилизационный сбор).
- По РФ: 86 000 ₽ брокер + комиссия 10% от суммы авто (авто + растаможка).
"""

import json
import math
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Константы по умолчанию (можно переопределить в config)
DOCUMENTS_KRW = 440_000       # Документы по Корее, платятся в крипте вместе с авто
FREIGHT_USD = 1000             # Фрахт, платится в крипте (USDT)
BROKER_RUB = 86_000            # Брокер по РФ
COMMISSION_RATE = 0.10        # 10% от суммы авто (авто в рублях + растаможка)


class PriceCalculator:
    def __init__(self, config_path: str = 'config.json'):
        self.config = self._load_config(config_path)
        self.exchange_rates = {}
        self.last_rate_update = 0

    def _load_config(self, config_path: str) -> Dict:
        """Загрузка конфигурации"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Конфиг не найден: {config_path}, используются умолчания")
            return {}
        except json.JSONDecodeError:
            return {}

    def _get_price_config(self) -> Dict:
        """Секция конфига для цен (по умолчанию — растаможка по ЦБ/постановлениям)."""
        return self.config.get("price", self._get_default_price_config())

    def _get_default_price_config(self) -> Dict:
        return {
            "cache_minutes": 5,
            "documents_krw": DOCUMENTS_KRW,
            "freight_usd": FREIGHT_USD,
            "broker_rub": BROKER_RUB,
            "commission_rate": COMMISSION_RATE,
            "customs": {
                "base_fee": 50000,
                "rate_per_cc": 0.05,
                "min_fee": 50000,
                "max_fee": 500000
            },
            "duty": {
                "rate": 0.15,
                "min_age_years": 3,
                "max_age_years": 10
            },
            "utilization": {
                "rate_per_cc": 0.02,
                "min_fee": 20000,
                "max_fee": 200000
            }
        }

    def get_krw_usdt_rate(self) -> float:
        """Курс: сколько KRW за 1 USDT. Binance USDTKRW может быть недоступен в регионе — тогда fallback из конфига или 1400."""
        key = "krw_per_usdt"
        if self._rate_cached(key):
            return self.exchange_rates[key]
        cfg = self._get_price_config()
        fallback = cfg.get("krw_per_usdt") or cfg.get("krw_per_usdt_fallback") or 1400.0
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTKRW", timeout=8)
            r.raise_for_status()
            krw_per_usdt = float(r.json()["price"])
            self.exchange_rates[key] = krw_per_usdt
            self._touch_cache()
            logger.info(f"KRW/USDT (за 1 USDT): {krw_per_usdt:.0f} KRW")
            return krw_per_usdt
        except Exception as e:
            logger.warning(f"KRW/USDT недоступен ({e}), используем {fallback:.0f} KRW")
            self.exchange_rates[key] = fallback
            self._touch_cache()
            return fallback

    def get_usdt_rub_rate(self) -> float:
        """Курс USDT → RUB (Binance USDTRUB)."""
        key = "usdt_rub"
        if self._rate_cached(key):
            return self.exchange_rates[key]
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTRUB", timeout=10)
            r.raise_for_status()
            rate = float(r.json()["price"])
            self.exchange_rates[key] = rate
            self._touch_cache()
            logger.info(f"USDT/RUB: {rate:.2f}")
            return rate
        except Exception as e:
            fallback = self._get_price_config().get("usdt_rub") or 95.0
            logger.warning(f"USDT/RUB недоступен ({e}), используем {fallback}")
            self.exchange_rates[key] = fallback
            self._touch_cache()
            return fallback

    def _rate_cached(self, key: str) -> bool:
        cfg = self._get_price_config()
        cache_m = cfg.get("cache_minutes", 5)
        return (time.time() - self.last_rate_update) < (cache_m * 60) and key in self.exchange_rates

    def _touch_cache(self) -> None:
        self.last_rate_update = time.time()

    def get_exchange_rate(self) -> float:
        """Совокупный курс KRW → RUB через USDT (1 KRW = ? RUB). Для обратной совместимости."""
        krw_per_usdt = self.get_krw_usdt_rate()
        usdt_rub = self.get_usdt_rub_rate()
        return usdt_rub / krw_per_usdt
    
    def _cfg(self, section: str, key: str, default: Any) -> Any:
        """Доступ к price-конфигу (растаможка по ЦБ/постановлениям)."""
        return self._get_price_config().get(section, {}).get(key, default)

    def get_cbr_eur_rub_safe(self) -> float:
        """Курс ЦБ РФ EUR/RUB (за 1 евро). Кэш как у остальных курсов."""
        key = "cbr_eur_rub"
        if self._rate_cached(key):
            return self.exchange_rates[key]
        try:
            r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=8)
            r.raise_for_status()
            data = r.json()
            eur = data.get("Valute", {}).get("EUR", {})
            nom = max(1, int(eur.get("Nominal", 1)))
            rate = float(eur.get("Value", 105)) / nom
            self.exchange_rates[key] = rate
            self._touch_cache()
            return rate
        except Exception as e:
            logger.warning(f"ЦБ EUR: {e}, используем 105")
            return self.exchange_rates.get(key, 105.0)

    # --- Растаможка по правилам 2026 (сбор за оформление, пошлина, утильсбор) ---

    # Тарифные сетки: стоимость авто в рублях -> сбор за таможенное оформление (2026)
    CUSTOMS_FEE_TIERS_RUB = [
        (200_000, 1_231),
        (450_000, 2_462),
        (1_200_000, 4_924),
        (2_700_000, 13_541),
        (4_200_000, 18_465),
        (5_500_000, 21_344),
        (10_000_000, 49_240),
        (float("inf"), 73_860),
    ]

    def calculate_customs_fee_tiered(self, car_value_rub: float) -> float:
        """Сбор за таможенное оформление (2026): по стоимости авто в рублях."""
        for limit, fee in self.CUSTOMS_FEE_TIERS_RUB:
            if car_value_rub <= limit:
                return fee
        return 73_860

    # Пошлина для физлиц, ДВС: возраст и объём двигателя -> EUR за см³ (2026)
    # до 1000, 1001-1500, 1501-1800, 1801-2300, 2301-3000, свыше 3001
    DUTY_EUR_PER_CC_3_5 = (1.5, 1.7, 2.5, 2.7, 3.0, 3.6)   # от 3 до 5 лет
    DUTY_EUR_PER_CC_5_PLUS = (3.0, 3.2, 3.5, 4.8, 5.0, 5.7)  # старше 5 лет

    def _engine_bracket_index(self, engine_cc: int) -> int:
        if engine_cc <= 1000: return 0
        if engine_cc <= 1500: return 1
        if engine_cc <= 1800: return 2
        if engine_cc <= 2300: return 3
        if engine_cc <= 3000: return 4
        return 5

    def calculate_duty_phys_eur_per_cc(self, engine_cc: int, age_years: int) -> float:
        """Пошлина физлицо ДВС: EUR за см³ по возрасту и объёму (2026). Возвращает EUR/см³."""
        idx = self._engine_bracket_index(engine_cc)
        if age_years < 3:
            return 0.0  # до 3 лет — процент от стоимости + мин, считаем отдельно при необходимости
        if age_years <= 5:
            return self.DUTY_EUR_PER_CC_3_5[idx]
        return self.DUTY_EUR_PER_CC_5_PLUS[idx]

    def calculate_duty_phys_under_3(self, car_value_eur: float, engine_cc: int) -> float:
        """Пошлина физлицо ДВС до 3 лет: 54%, но не менее 2.5 EUR/см³ (упрощённо — мин по объёму)."""
        eur_per_cc = 2.5
        by_percent = car_value_eur * 0.54
        by_cc = engine_cc * eur_per_cc
        return max(by_percent, by_cc)

    # Утильсбор 2026: БС = 20 000 ₽, К — коэффициент. Физлицо личное: ≤3000 см³ и ≤117.68 кВт -> 0.17 (<3), 0.26 (≥3)
    UTIL_BASE_PERSONAL = 20_000
    # Иначе коэффициент по таблице (физлицо перепродажа / усреднённо по объёму и возрасту)
    UTIL_COEF_BY_ENGINE_AGE = {
        (0, 0): 0.17, (0, 1): 0.26,   # до 1000
        (1, 0): 0.17, (1, 1): 0.26,   # 1001-2000
        (2, 0): 0.17, (2, 1): 0.26,   # 2001-3000
        (3, 0): 129.2, (3, 1): 197.81,
        (4, 0): 164.53, (4, 1): 219.48,
    }

    def _parse_power_hp(self, car_data: Dict[str, Any]) -> Optional[float]:
        """Мощность в л.с. из данных (для утильсбора: 117.68 кВт ≈ 160 л.с.)."""
        p = car_data.get("power") or car_data.get("power_hp") or car_data.get("outputHorsepower")
        if p is None:
            return None
        s = "".join(c for c in str(p) if c.isdigit() or c in ".,")
        if not s:
            return None
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None

    def calculate_utilization_2026(self, engine_cc: int, age_years: int, power_hp: Optional[float]) -> float:
        """Утилизационный сбор (2026): БС × К. Физлицо личное — льготный К при объёме ≤3000 и мощность ≤160 л.с."""
        base = self.UTIL_BASE_PERSONAL
        if engine_cc <= 3000 and (power_hp is None or power_hp <= 160):
            k = 0.17 if age_years < 3 else 0.26
            return base * k
        idx = min(self._engine_bracket_index(engine_cc), 4)
        age_bucket = 0 if age_years < 3 else 1
        k = self.UTIL_COEF_BY_ENGINE_AGE.get((idx, age_bucket))
        if k is None:
            k = 112.52 if age_bucket == 0 else 170.36
        return base * k

    def calculate_customs_fee(self, price_won: float, engine_volume: int) -> float:
        """Устаревший: для совместимости. Используйте calculate_customs_fee_tiered(car_value_rub)."""
        return 4924  # типовой диапазон

    def calculate_duty(self, price_won: float, age_years: int) -> float:
        """Устаревший метод. Используйте расчёт по EUR/см³ и курсу ЦБ."""
        return 0.0

    def calculate_utilization_fee(self, engine_volume: int) -> float:
        """Устаревший метод. Используйте calculate_utilization_2026."""
        return self.UTIL_BASE_PERSONAL * 0.26

    def calculate_total_cost(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Полный расчет по новой схеме:
        - Стоимость авто из выгрузки (price_won в 10k вон).
        - Конвертация KRW→USDT→RUB: (авто + 440k KRW) и отдельно 1000 $ фрахт.
        - Растаможка по ЦБ/постановлениям (сбор + пошлина + утилизационный).
        - 86 000 ₽ брокер + 10% от (авто в рублях + растаможка).
        """
        cfg = self._get_price_config()
        documents_krw = cfg.get("documents_krw", DOCUMENTS_KRW)
        freight_usd = cfg.get("freight_usd", FREIGHT_USD)
        broker_rub = cfg.get("broker_rub", BROKER_RUB)
        commission_rate = cfg.get("commission_rate", COMMISSION_RATE)

        # Цена авто из выгрузки: в выгрузке price_won хранится в единицах 10k вон (например 3000 = 30 млн ₩)
        price_won_10k = car_data.get("price_won")
        if price_won_10k is None and "price" in car_data:
            try:
                p = car_data["price"]
                price_won_10k = int(p) if isinstance(p, (int, float)) else int(str(p).replace(" ", ""))
            except (TypeError, ValueError):
                price_won_10k = 0
        if price_won_10k is None:
            price_won_10k = 0
        price_won = float(price_won_10k * 10000)  # полные воны

        # Курсы крипты
        krw_per_usdt = self.get_krw_usdt_rate()
        usdt_rub = self.get_usdt_rub_rate()
        # 1 KRW = (1 / krw_per_usdt) USDT = (1 / krw_per_usdt) * usdt_rub RUB
        krw_to_rub = usdt_rub / krw_per_usdt

        # В крипте: авто + документы Корея (440k KRW)
        amount_krw_with_docs = price_won + documents_krw
        car_and_docs_rub = amount_krw_with_docs * krw_to_rub
        # Фрахт 1000 $ в крипте
        freight_rub = freight_usd * usdt_rub

        # Сумма "авто в рублях" (то, что платится в крипте за машину и доставку до РФ)
        car_rub = car_and_docs_rub
        price_rub_display = car_rub  # для отображения как "стоимость авто в руб"

        # Растаможка по правилам 2026 (сбор за оформление, пошлина, утильсбор)
        engine_volume = int(car_data.get("engine_volume") or car_data.get("displacement") or 2000)
        if isinstance(engine_volume, str):
            engine_volume = int("".join(c for c in str(engine_volume) if c.isdigit()) or 2000)
        year = car_data.get("year") or car_data.get("Year") or (datetime.now().year - 5)
        if isinstance(year, str):
            year = int("".join(c for c in str(year) if c.isdigit()) or (datetime.now().year - 5))
        age_years = max(0, datetime.now().year - year)
        power_hp = self._parse_power_hp(car_data)

        # 1) Сбор за таможенное оформление — по стоимости авто в рублях (2026)
        customs_fee = self.calculate_customs_fee_tiered(car_rub)

        # 2) Пошлина: курс ЦБ EUR/RUB; физлицо ДВС по возрасту и объёму
        eur_rub = self.get_cbr_eur_rub_safe()
        if age_years < 3:
            car_value_eur = car_rub / eur_rub
            duty_eur = self.calculate_duty_phys_under_3(car_value_eur, engine_volume)
            duty = duty_eur * eur_rub
        else:
            eur_per_cc = self.calculate_duty_phys_eur_per_cc(engine_volume, age_years)
            duty = engine_volume * eur_per_cc * eur_rub

        # 3) Утилизационный сбор (2026): базовая ставка × коэффициент
        utilization = self.calculate_utilization_2026(engine_volume, age_years, power_hp)
        customs_total = customs_fee + duty + utilization

        # Сумма авто (для комиссии): авто в руб + растаможка
        vehicle_sum = car_rub + freight_rub + customs_total
        commission = vehicle_sum * commission_rate
        total_with_commission = vehicle_sum + broker_rub + commission

        return {
            "price_won": price_won,
            "price_rub": price_rub_display,
            "documents_krw_rub": documents_krw * krw_to_rub,
            "freight_rub": freight_rub,
            "krw_per_usdt": krw_per_usdt,
            "usdt_rub": usdt_rub,
            "eur_rub": eur_rub,
            "customs_fee": customs_fee,
            "duty": duty,
            "utilization": utilization,
            "customs_total": customs_total,
            "broker_rub": broker_rub,
            "commission": commission,
            "commission_rate": commission_rate,
            "vehicle_sum": vehicle_sum,
            "total_with_commission": total_with_commission,
        }
    
    def update_car_with_prices(self, car_data: Dict[str, Any]) -> Dict[str, Any]:
        """Дополняет данные авто рассчитанными полями по новой схеме (KRW→USDT→RUB, растаможка, брокер, 10%)."""
        prices = self.calculate_total_cost(car_data)
        car_data["price_rub_estimate"] = prices["price_rub"]
        car_data["documents_krw_rub"] = prices.get("documents_krw_rub", 0)
        car_data["freight_rub"] = prices["freight_rub"]
        car_data["customs_fee_rub"] = prices["customs_fee"]
        car_data["duty_rub"] = prices["duty"]
        car_data["util_rub"] = prices["utilization"]
        car_data["customs_total_rub"] = prices["customs_total"]
        car_data["broker_rub"] = prices["broker_rub"]
        car_data["commission_rub"] = prices["commission"]
        car_data["vehicle_sum_rub"] = prices["vehicle_sum"]
        car_data["my_price"] = prices["total_with_commission"]
        car_data["krw_per_usdt"] = prices.get("krw_per_usdt")
        car_data["usdt_rub"] = prices.get("usdt_rub")
        return car_data

def main():
    """Проверка расчёта: авто из выгрузки, KRW→USDT→RUB, 440k KRW + 1000$ в крипте, растаможка, 86k + 10%."""
    calculator = PriceCalculator()
    # Как в выгрузке: price_won в единицах 10k вон (3000 = 30 млн ₩)
    test_car = {
        "price_won": 3000,
        "engine_volume": 2000,
        "year": 2019,
    }
    prices = calculator.calculate_total_cost(test_car)
    print("Расчёт стоимости (авто из выгрузки, крипта KRW→USDT→RUB, растаможка, 86k + 10%):")
    print(f"  Цена авто (выгрузка): {prices['price_won']:,.0f} ₩")
    print(f"  Курс: 1 USDT = {prices['krw_per_usdt']:,.0f} KRW, 1 USDT = {prices['usdt_rub']:.2f} ₽")
    print(f"  Авто + документы 440k KRW в рублях: {prices['price_rub']:,.0f} ₽")
    print(f"  Фрахт 1000 $ в рублях: {prices['freight_rub']:,.0f} ₽")
    print(f"  Таможенный сбор: {prices['customs_fee']:,.0f} ₽")
    print(f"  Пошлина: {prices['duty']:,.0f} ₽")
    print(f"  Утилизационный сбор: {prices['utilization']:,.0f} ₽")
    print(f"  Растаможка итого: {prices['customs_total']:,.0f} ₽")
    print(f"  Сумма авто (авто+фрахт+растаможка): {prices['vehicle_sum']:,.0f} ₽")
    print(f"  Брокер: {prices['broker_rub']:,.0f} ₽")
    print(f"  Комиссия {prices['commission_rate']*100:.0f}%: {prices['commission']:,.0f} ₽")
    print(f"  Итоговая цена: {prices['total_with_commission']:,.0f} ₽")

if __name__ == "__main__":
    main()