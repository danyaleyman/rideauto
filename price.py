#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расчет стоимости автомобиля с учетом всех платежей и комиссий
"""

import json
import math
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PriceCalculator:
    def __init__(self, config_path: str = 'config.json'):
        """
        Инициализация калькулятора цен
        
        Args:
            config_path: путь к файлу конфигурации
        """
        self.config = self._load_config(config_path)
        self.exchange_rates = {}
        self.last_rate_update = 0
        
    def _load_config(self, config_path: str) -> Dict:
        """Загрузка конфигурации"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Конфигурационный файл не найден: {config_path}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Получение конфигурации по умолчанию"""
        return {
            "exchange_rate": {
                "source": "binance",
                "base_currency": "USDT",
                "target_currency": "RUB",
                "cache_minutes": 5
            },
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
            },
            "export": {
                "base_fee": 30000,
                "documents_fee": 20000
            },
            "freight": {
                "base_fee": 100000,
                "per_cc": 0.01,
                "insurance_rate": 0.01
            },
            "broker": {
                "base_fee": 50000,
                "rate": 0.02
            },
            "reserve": {
                "rate": 0.05
            },
            "avtovoz": {
                "base_fee": 80000,
                "per_km": 100
            },
            "insurance": {
                "base_fee": 30000,
                "rate": 0.01
            },
            "commission": {
                "rate": 0.10
            }
        }
    
    def get_exchange_rate(self) -> float:
        """
        Получение актуального курса обмена
        
        Returns:
            float: курс обмена
        """
        current_time = time.time()
        
        # Проверка кэша
        cache_minutes = self.config.get("exchange_rate", {}).get("cache_minutes", 5)
        if current_time - self.last_rate_update < cache_minutes * 60:
            return self.exchange_rates.get("rate", 1.0)
        
        try:
            exchange_config = self.config.get("exchange_rate", {})
            source = exchange_config.get("source", "binance")
            
            if source == "binance":
                rate = self._get_binance_rate()
            elif source == "cbr":
                rate = self._get_cbr_rate()
            else:
                rate = self._get_binance_rate()  # fallback
            
            self.exchange_rates["rate"] = rate
            self.last_rate_update = current_time
            logger.info(f"Обновлен курс обмена: {rate}")
            
        except Exception as e:
            logger.error(f"Ошибка получения курса: {e}")
            rate = self.exchange_rates.get("rate", 1.0)
        
        return rate
    
    def _get_binance_rate(self) -> float:
        """Получение курса с Binance"""
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={self.config['exchange_rate']['base_currency']}{self.config['exchange_rate']['target_currency']}"
        response = requests.get(url, timeout=10)
        data = response.json()
        return float(data["price"])
    
    def _get_cbr_rate(self) -> float:
        """Получение курса с ЦБ РФ"""
        # Реализация получения курса с ЦБ РФ
        # Пока возвращаем заглушку
        return 90.0
    
    def calculate_customs_fee(self, price_won: float, engine_volume: int) -> float:
        """
        Расчет таможенного сбора
        
        Args:
            price_won: цена в вонах
            engine_volume: объем двигателя в см3
            
        Returns:
            float: таможенный сбор в рублях
        """
        customs_config = self.config.get("customs", {})
        base_fee = customs_config.get("base_fee", 50000)
        rate_per_cc = customs_config.get("rate_per_cc", 0.05)
        min_fee = customs_config.get("min_fee", 50000)
        max_fee = customs_config.get("max_fee", 500000)
        
        fee = base_fee + (engine_volume * rate_per_cc)
        fee = max(min_fee, min(fee, max_fee))
        
        return fee
    
    def calculate_duty(self, price_won: float, age_years: int) -> float:
        """
        Расчет единого таможенного платежа
        
        Args:
            price_won: цена в вонах
            age_years: возраст автомобиля в годах
            
        Returns:
            float: таможенный платеж в рублях
        """
        duty_config = self.config.get("duty", {})
        min_age_years = duty_config.get("min_age_years", 3)
        max_age_years = duty_config.get("max_age_years", 10)
        
        if age_years < min_age_years or age_years > max_age_years:
            return 0
        
        rate = duty_config.get("rate", 0.15)
        return price_won * rate
    
    def calculate_utilization_fee(self, engine_volume: int) -> float:
        """
        Расчет утилизационного сбора
        
        Args:
            engine_volume: объем двигателя в см3
            
        Returns:
            float: утилизационный сбор в рублях
        """
        utilization_config = self.config.get("utilization", {})
        rate_per_cc = utilization_config.get("rate_per_cc", 0.02)
        min_fee = utilization_config.get("min_fee", 20000)
        max_fee = utilization_config.get("max_fee", 200000)
        
        fee = engine_volume * rate_per_cc
        fee = max(min_fee, min(fee, max_fee))
        
        return fee
    
    def calculate_export_costs(self) -> float:
        """Расчет экспортных документов"""
        export_config = self.config.get("export", {})
        base_fee = export_config.get("base_fee", 30000)
        documents_fee = export_config.get("documents_fee", 20000)
        return base_fee + documents_fee
    
    def calculate_freight(self, price_won: float, distance_km: int = 1000) -> float:
        """
        Расчет стоимости фрахта
        
        Args:
            price_won: цена в вонах
            distance_km: расстояние в км
            
        Returns:
            float: стоимость фрахта в рублях
        """
        freight_config = self.config.get("freight", {})
        base_fee = freight_config.get("base_fee", 100000)
        per_cc = freight_config.get("per_cc", 0.01)
        insurance_rate = freight_config.get("insurance_rate", 0.01)
        
        freight = base_fee + (distance_km * per_cc)
        insurance = price_won * insurance_rate
        
        return freight + insurance
    
    def calculate_broker_fee(self, price_won: float) -> float:
        """
        Расчет брокерских услуг
        
        Args:
            price_won: цена в вонах
            
        Returns:
            float: брокерские услуги в рублях
        """
        broker_config = self.config.get("broker", {})
        base_fee = broker_config.get("base_fee", 50000)
        rate = broker_config.get("rate", 0.02)
        
        return base_fee + (price_won * rate)
    
    def calculate_reserve(self, total_cost: float) -> float:
        """Расчет резерва"""
        reserve_config = self.config.get("reserve", {})
        rate = reserve_config.get("rate", 0.05)
        return total_cost * rate
    
    def calculate_avtovoz(self, distance_km: int = 1000) -> float:
        """
        Расчет стоимости автовоза
        
        Args:
            distance_km: расстояние в км
            
        Returns:
            float: стоимость автовоза в рублях
        """
        avtovoz_config = self.config.get("avtovoz", {})
        base_fee = avtovoz_config.get("base_fee", 80000)
        per_km = avtovoz_config.get("per_km", 100)
        
        return base_fee + (distance_km * per_km)
    
    def calculate_insurance(self, price_won: float) -> float:
        """
        Расчет страховки
        
        Args:
            price_won: цена в вонах
            
        Returns:
            float: страховка в рублях
        """
        insurance_config = self.config.get("insurance", {})
        base_fee = insurance_config.get("base_fee", 30000)
        rate = insurance_config.get("rate", 0.01)
        
        return base_fee + (price_won * rate)
    
    def calculate_commission(self, total_cost: float) -> float:
        """Расчет комиссии"""
        commission_config = self.config.get("commission", {})
        rate = commission_config.get("rate", 0.10)
        return total_cost * rate
    
    def calculate_total_cost(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Полный расчет стоимости автомобиля
        
        Args:
            car_data: данные об автомобиле
            
        Returns:
            Dict: все рассчитанные стоимости
        """
        # Конвертация цены в рубли
        price_won = car_data.get("price_won", 0) * 10000  # конвертация из 10k вон
        exchange_rate = self.get_exchange_rate()
        price_rub = price_won * exchange_rate
        
        # Характеристики автомобиля
        engine_volume = car_data.get("engine_volume", 2000)
        age_years = car_data.get("age_years", 5)
        
        # Расчет всех платежей
        customs_fee = self.calculate_customs_fee(price_won, engine_volume)
        duty = self.calculate_duty(price_won, age_years)
        utilization = self.calculate_utilization_fee(engine_volume)
        export_costs = self.calculate_export_costs()
        freight = self.calculate_freight(price_won)
        broker = self.calculate_broker_fee(price_won)
        avtovoz = self.calculate_avtovoz()
        insurance = self.calculate_insurance(price_won)
        
        # Сумма без комиссии
        total_no_commission = (price_rub + customs_fee + duty + utilization + 
                             export_costs + freight + broker + avtovoz + insurance)
        
        # Резерв
        reserve = self.calculate_reserve(total_no_commission)
        total_with_reserve = total_no_commission + reserve
        
        # Комиссия
        commission = self.calculate_commission(total_with_reserve)
        total_with_commission = total_with_reserve + commission
        
        return {
            "price_won": price_won,
            "price_rub": price_rub,
            "exchange_rate": exchange_rate,
            "customs_fee": customs_fee,
            "duty": duty,
            "utilization": utilization,
            "export_costs": export_costs,
            "freight": freight,
            "broker": broker,
            "avtovoz": avtovoz,
            "insurance": insurance,
            "total_no_commission": total_no_commission,
            "reserve": reserve,
            "total_with_reserve": total_with_reserve,
            "commission": commission,
            "total_with_commission": total_with_commission
        }
    
    def update_car_with_prices(self, car_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обновление данных автомобиля рассчитанными ценами
        
        Args:
            car_data: исходные данные об автомобиле
            
        Returns:
            Dict: обновленные данные с ценами
        """
        prices = self.calculate_total_cost(car_data)
        
        # Добавляем рассчитанные цены к данным автомобиля
        car_data["price_rub_estimate"] = prices["price_rub"]
        car_data["customs_fee_rub"] = prices["customs_fee"]
        car_data["duty_rub"] = prices["duty"]
        car_data["util_rub"] = prices["utilization"]
        car_data["export_rub"] = prices["export_costs"]
        car_data["freight_rub"] = prices["freight"]
        car_data["broker_rub"] = prices["broker"]
        car_data["avtovoz_rub"] = prices["avtovoz"]
        car_data["insurance_rub"] = prices["insurance"]
        car_data["total_cost_no_commission"] = prices["total_no_commission"]
        car_data["reserve_rub"] = prices["reserve"]
        car_data["my_price"] = prices["total_with_commission"]
        
        return car_data

def main():
    """Основная функция для тестирования"""
    calculator = PriceCalculator()
    
    # Пример данных об автомобиле
    test_car = {
        "price_won": 3000,  # 30 млн вон
        "engine_volume": 2000,
        "age_years": 5
    }
    
    # Расчет стоимости
    prices = calculator.calculate_total_cost(test_car)
    
    # Вывод результатов
    print("Расчет стоимости автомобиля:")
    print(f"Цена в вонах: {test_car['price_won']} млн ₩")
    print(f"Курс обмена: {prices['exchange_rate']}")
    print(f"Цена в рублях: {prices['price_rub']:,.0f} ₽")
    print(f"Таможенный сбор: {prices['customs_fee']:,.0f} ₽")
    print(f"Единый платеж: {prices['duty']:,.0f} ₽")
    print(f"Утилизационный сбор: {prices['utilization']:,.0f} ₽")
    print(f"Экспортные документы: {prices['export_costs']:,.0f} ₽")
    print(f"Фрахт: {prices['freight']:,.0f} ₽")
    print(f"Брокер: {prices['broker']:,.0f} ₽")
    print(f"Автовоз: {prices['avtovoz']:,.0f} ₽")
    print(f"Страховка: {prices['insurance']:,.0f} ₽")
    print(f"Всего без комиссии: {prices['total_no_commission']:,.0f} ₽")
    print(f"Резерв: {prices['reserve']:,.0f} ₽")
    print(f"Комиссия (10%): {prices['commission']:,.0f} ₽")
    print(f"Итоговая цена: {prices['total_with_commission']:,.0f} ₽")

if __name__ == "__main__":
    main()