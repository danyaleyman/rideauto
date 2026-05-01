#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расчёт стоимости автомобиля под ввоз (физлицо, личное пользование).

Схема платежей:
- Стоимость из выгрузки: price_won в единицах 10 000 KRW.
- Конвертация в крипте: KRW → USDT → RUB (как раньше).
- В крипте фиксировано: DOCUMENTS_KRW (документы Корея), FREIGHT_USD (фрахт).
- Растаможка РФ: таможенный сбор, пошлина, утилизационный сбор.
- Для режима физлица (личное пользование) акциз и НДС не начисляются.
- Брокер BROKER_RUB и комиссия (10%% от базы или ≈400 000 ₽ для дорогих авто).

Правила пошлины / утиля ориентированы на режим физлиц ЕАЭС 2026 и официальные
ставки (единые ставки ЕТС €/см³, шкала для авто младше 3 лет).
Точные суммы перед сделкой сверяйте с таможней и актуальными ПП РФ / решениями ЕЭК.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Платежи «в крипте» (без изменений по смыслу) ---
DOCUMENTS_KRW = 440_000
FREIGHT_USD = 1000
BROKER_RUB = 86_000
CHINA_DOCS_DELIVERY_CNY = 13_500
CHINA_BROKER_RUB = 86_100
COMMISSION_RATE_DEFAULT = 0.10
# Порог «дорогого» авто (только цена авто+доки в ₽) для фиксированной комиссии
COMMISSION_CAR_RUB_THRESHOLD = 4_000_000
COMMISSION_CAP_TARGET_RUB = 400_000
COMMISSION_CAP_ROUND_RUB = 1000

# Базовая ставка утилизационного сбора для физлиц (личное пользование), ₽
UTIL_BASE_PERSONAL_RUB = 20_000

# Пошлина физлица 3–5 лет / старше 5 лет: EUR за 1 см³ по объёму (ЕТС ЕАЭС, актуально для 2026)
DUTY_EUR_PER_CC_3_5: Tuple[float, ...] = (1.5, 1.7, 2.5, 2.7, 3.0, 3.6)
DUTY_EUR_PER_CC_5_PLUS: Tuple[float, ...] = (3.0, 3.2, 3.5, 4.8, 5.0, 5.7)

# Младше 3 лет: верхняя граница стоимости авто в EUR → (ставка %% от стоимости, мин. EUR/см³)
# Источник: единые ставки ввоза для физлиц (типовая таблица 2025–2026).
DUTY_UNDER3_EUR_TIERS: List[Tuple[float, float, float]] = [
    (8500.0, 0.54, 2.5),
    (16700.0, 0.48, 3.5),
    (42300.0, 0.48, 5.5),
    (84500.0, 0.48, 7.5),
    (169000.0, 0.48, 15.0),
    (float("inf"), 0.48, 20.0),
]

# Таможенный сбор за оформление: стоимость авто в ₽ → сбор (типовые ступени 2026)
CUSTOMS_FEE_TIERS_RUB: List[Tuple[float, float]] = [
    (200_000, 1_231),
    (450_000, 2_462),
    (1_200_000, 4_924),
    (2_700_000, 13_541),
    (4_200_000, 18_465),
    (5_500_000, 21_344),
    (10_000_000, 49_240),
    (float("inf"), 73_860),
]

# Льготный утиль: для физлица (личное пользование) при мощности ДВС ≤ 160 л.с.
UTIL_HP_THRESHOLD = 160

# Коэффициенты утилизации при превышении порога по объёму или мощности ДВС.
# Ключ: индекс объёма (как для пошлины 0..5), возрастная группа 0 = <3 лет, 1 = ≥3 лет.
# Значения — как в прежней версии калькулятора; для старших объёмов — расширение по аналогии.
UTIL_COEF_BY_ENGINE_AGE: Dict[Tuple[int, int], float] = {
    (0, 0): 0.17,
    (0, 1): 0.26,
    (1, 0): 0.17,
    (1, 1): 0.26,
    (2, 0): 0.17,
    (2, 1): 0.26,
    (3, 0): 129.2,
    (3, 1): 197.81,
    (4, 0): 164.53,
    (4, 1): 219.48,
    (5, 0): 180.0,
    (5, 1): 245.0,
}

# НК РФ ст. 193: справочные ставки акциза по мощности двигателя (руб./л.с.).
# В текущем расчёте для физлица/личного пользования акциз не начисляется.
# Таблица сохранена только для совместимости конфига и дальнейшего расширения.
EXCISE_HP_TIERS_RUB_PER_HP: List[Tuple[float, float]] = [
    (90.0, 0.0),
    (150.0, 64.0),
    (200.0, 613.0),
    (300.0, 1004.0),
    (400.0, 1711.0),
    (500.0, 1771.0),
    (float("inf"), 1829.0),
]

# Постановление №1291 (ред. 2025/2026): для мощных авто применяем
# повышающий коэффициент к базовому расчёту утиля.
UTIL_POWER_MULTIPLIER_TIERS: List[Tuple[float, float]] = [
    (160.0, 1.0),
    (200.0, 1.1),
    (250.0, 1.25),
    (300.0, 1.45),
    (float("inf"), 1.7),
]


def engine_volume_bracket_index(engine_cc: int) -> int:
    """Индекс 0..5 по объёму для таблиц €/см³ и утиля."""
    if engine_cc <= 1000:
        return 0
    if engine_cc <= 1500:
        return 1
    if engine_cc <= 1800:
        return 2
    if engine_cc <= 2300:
        return 3
    if engine_cc <= 3000:
        return 4
    return 5


def classify_fuel(car_data: Dict[str, Any]) -> str:
    """
    electric | hybrid | ice
    - electric: только электротяга (утиль и пошлина по электро-правилам).
    - hybrid: гибрид; для пошлины/утиля используем объём и мощность ДВС (см. ice_engine_inputs).
    - ice: бензин / дизель / газ и т.п.
    """
    raw = (
        car_data.get("engine_type")
        or car_data.get("fuel")
        or car_data.get("engineType")
        or ""
    )
    s = str(raw).lower()
    ko = str(raw)

    if "전기" in ko and "가솔린" not in ko and "디젤" not in ko and "하이브리드" not in ko:
        return "electric"
    if "electric" in s or s.strip() == "ev" or "электро" in s:
        return "electric"

    if (
        "hybrid" in s
        or "hev" in s
        or "phev" in s
        or "plug" in s
        or "하이브리드" in ko
        or ("가솔린" in ko and "전기" in ko)
        or ("디젤" in ko and "전기" in ko)
        or "гибрид" in s
    ):
        return "hybrid"

    return "ice"


def ice_engine_inputs(car_data: Dict[str, Any], fuel: str) -> Tuple[int, Optional[float]]:
    """
    Объём (см³) и мощность ДВС (л.с.) для пошлины и утиля.
    Для гибрида: в данных Encar часто одна мощность на всю установку — без поля «только ДВС»
    берём указанную мощность как оценку (серийный генератор не выделяется).
    """
    disp = (
        car_data.get("engine_volume")
        or car_data.get("displacement")
        or car_data.get("displacement_cc")
        or car_data.get("displacement_label")
        or car_data.get("dongchedi_displacement_label")
    )
    engine_cc = parse_engine_cc(disp)

    if fuel == "electric":
        return 0, None

    hp = parse_power_hp(car_data)
    if fuel == "hybrid" and car_data.get("power_ice_hp") is not None:
        try:
            hp = float(car_data["power_ice_hp"])
        except (TypeError, ValueError):
            pass

    return engine_cc, hp


def parse_power_hp(car_data: Dict[str, Any]) -> Optional[float]:
    p = car_data.get("power") or car_data.get("power_hp") or car_data.get("outputHorsepower")
    if p is None:
        kw = car_data.get("power_kw")
        if kw is not None:
            try:
                v = float(kw)
                if v > 0:
                    return v / 0.7355
            except (TypeError, ValueError):
                pass
        return None
    s = "".join(c for c in str(p) if c.isdigit() or c in ".,")
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def parse_engine_cc(v: Any) -> int:
    if v is None or v == "":
        return 0
    if isinstance(v, (int, float)):
        iv = int(v)
        return iv if iv > 0 else 0
    s = str(v).strip().replace(",", ".")
    if not s:
        return 0
    up = s.upper()
    try:
        if "T" in up or "L" in up:
            num = "".join(ch for ch in up if ch.isdigit() or ch == ".")
            if not num:
                return 0
            liters = float(num)
            cc = int(round(liters * 1000))
            return cc if cc > 0 else 0
        digits = "".join(ch for ch in up if ch.isdigit())
        if not digits:
            return 0
        iv = int(digits)
        # 15/20/25 обычно значит 1.5/2.0/2.5L из короткой записи.
        if iv < 100 and "." not in up:
            return iv * 100
        return iv
    except (TypeError, ValueError):
        return 0


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


def customs_fee(car_value_rub: float) -> float:
    """Таможенный сбор за оформление (ступени по таможенной стоимости в ₽)."""
    for limit, fee in CUSTOMS_FEE_TIERS_RUB:
        if car_value_rub <= limit:
            return fee
    return CUSTOMS_FEE_TIERS_RUB[-1][1]


def duty_phys_person_rub(
    *,
    car_value_rub: float,
    eur_rub: float,
    engine_cc: int,
    age_years: int,
    fuel: str,
) -> float:
    """
    Ввозная пошлина физлица в ₽.
    - electric: 0
    - ice / hybrid: ДВС — шкала <3 лет (%% и мин. €/см³) или €/см³ для 3–5 и 5+ лет.
    """
    if fuel == "electric":
        return 0.0

    if engine_cc <= 0:
        logger.warning("Объём ДВС не задан для не-EV — условно 2000 см³")
        engine_cc = 2000

    car_value_eur = car_value_rub / eur_rub if eur_rub > 0 else 0.0

    if age_years < 3:
        duty_eur = 0.0
        for limit_eur, pct, min_eur_cc in DUTY_UNDER3_EUR_TIERS:
            if car_value_eur <= limit_eur:
                duty_eur = max(car_value_eur * pct, engine_cc * min_eur_cc)
                break
        return duty_eur * eur_rub

    idx = engine_volume_bracket_index(engine_cc)
    if age_years <= 5:
        eur_per_cc = DUTY_EUR_PER_CC_3_5[idx]
    else:
        eur_per_cc = DUTY_EUR_PER_CC_5_PLUS[idx]
    return engine_cc * eur_per_cc * eur_rub


def utilization_phys_person_rub(
    *,
    engine_cc: int,
    age_years: int,
    power_hp_ice: Optional[float],
    fuel: str,
) -> float:
    """
    Утилизационный сбор физлица (личное пользование).
    - electric: 0
    - льгота физлица: мощность ДВС ≤ 160 л.с. → 3400 ₽ (<3 лет) или 5200 ₽ (≥3 лет)
    - иначе: коэффициент по объёму/возрасту с повышающим множителем по мощности
    """
    if fuel == "electric":
        return 0.0

    if engine_cc <= 0:
        engine_cc = 2000

    age_bucket = 0 if age_years < 3 else 1
    hp_ok = power_hp_ice is None or power_hp_ice <= UTIL_HP_THRESHOLD
    if hp_ok:
        k = 0.17 if age_bucket == 0 else 0.26
        return UTIL_BASE_PERSONAL_RUB * k

    idx = engine_volume_bracket_index(engine_cc)
    k = UTIL_COEF_BY_ENGINE_AGE.get((idx, age_bucket))
    if k is None:
        k = UTIL_COEF_BY_ENGINE_AGE.get((min(idx, 5), age_bucket), 112.52 if age_bucket == 0 else 170.36)
    power_mult = 1.0
    if power_hp_ice is not None:
        for hp_limit, mult in UTIL_POWER_MULTIPLIER_TIERS:
            if power_hp_ice <= hp_limit:
                power_mult = mult
                break
    return UTIL_BASE_PERSONAL_RUB * k * power_mult


def excise_rub(power_hp: Optional[float], hp_tiers: Optional[List[Tuple[float, float]]] = None) -> float:
    """
    Акциз для физлица/личного пользования не начисляется.
    """
    _ = power_hp, hp_tiers
    return 0.0


def vat_import_rub(
    car_value_rub: float,
    duty_rub: float,
    excise_value_rub: float,
    *,
    fuel: str,
    age_years: int,
) -> float:
    """
    НДС для физлица/личного пользования не начисляется.
    """
    _ = car_value_rub, duty_rub, excise_value_rub, fuel, age_years
    return 0.0


def commission_rub(
    car_value_rub: float,
    customs_total_rub: float,
    broker_rub: float,
    rate_default: float = COMMISSION_RATE_DEFAULT,
) -> Tuple[float, float]:
    """
    Комиссия.
    База для процента: авто (₽) + растаможка (сбор+пошлина+утиль+НДС) + брокер.
    - Если car_value_rub ≤ 4M: комиссия = rate_default × база
    - Иначе: комиссия ≈ 400_000 ₽, округление до 1000 ₽
    Возвращает (commission, effective_rate_for_info).
    """
    anchor = car_value_rub + customs_total_rub + broker_rub
    if car_value_rub <= COMMISSION_CAR_RUB_THRESHOLD:
        comm = anchor * rate_default
        eff = rate_default
    else:
        comm = round(COMMISSION_CAP_TARGET_RUB / COMMISSION_CAP_ROUND_RUB) * COMMISSION_CAP_ROUND_RUB
        eff = comm / anchor if anchor > 0 else 0.0
    return comm, eff


def parse_year(car_data: Dict[str, Any]) -> int:
    y = car_data.get("year") or car_data.get("Year") or datetime.now().year - 5
    if isinstance(y, str):
        digits = "".join(c for c in y if c.isdigit())
        y = int(digits[:4]) if len(digits) >= 4 else datetime.now().year - 5
    return int(y)


def age_years_car(year: int) -> int:
    return max(0, datetime.now().year - year)


class PriceCalculator:
    """Оркестратор курсов и полного расчёта (совместимость с export / фронтом)."""

    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.exchange_rates: Dict[str, float] = {}
        self.last_rate_update = 0.0

    def _load_config(self, config_path: str) -> Dict:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Конфиг не найден: %s, умолчания", config_path)
            return {}
        except json.JSONDecodeError:
            return {}

    def _get_price_config(self) -> Dict:
        return self.config.get("price", self._get_default_price_config())

    def _get_default_price_config(self) -> Dict:
        return {
            "cache_minutes": 5,
            "documents_krw": DOCUMENTS_KRW,
            "freight_usd": FREIGHT_USD,
            "broker_rub": BROKER_RUB,
            "china_docs_delivery_cny": CHINA_DOCS_DELIVERY_CNY,
            "china_broker_rub": CHINA_BROKER_RUB,
            "commission_rate": COMMISSION_RATE_DEFAULT,
            "excise_hp_tiers_rub_per_hp": [[hp, rate] for hp, rate in EXCISE_HP_TIERS_RUB_PER_HP],
        }

    def get_krw_usdt_rate(self) -> float:
        key = "krw_per_usdt"
        if self._rate_cached(key):
            return self.exchange_rates[key]
        cfg = self._get_price_config()
        fallback = float(cfg.get("krw_per_usdt") or cfg.get("krw_per_usdt_fallback") or 1400.0)
        try:
            # На Binance споте пары USDTKRW часто нет (400) — сначала USD→KRW как прокси для USDT.
            r = requests.get(
                "https://api.binance.com/api/v3/ticker/price?symbol=USDTKRW", timeout=8
            )
            if r.ok:
                krw_per_usdt = float(r.json()["price"])
            else:
                r.raise_for_status()
            self.exchange_rates[key] = krw_per_usdt
            self._touch_cache()
            logger.info("KRW/USDT (за 1 USDT): %.0f KRW", krw_per_usdt)
            return krw_per_usdt
        except Exception as e_binance:
            try:
                r2 = requests.get(
                    "https://api.frankfurter.app/latest?from=USD&to=KRW", timeout=8
                )
                r2.raise_for_status()
                krw_per_usdt = float(r2.json().get("rates", {}).get("KRW") or 0)
                if krw_per_usdt <= 0:
                    raise ValueError("no KRW in frankfurter response")
                self.exchange_rates[key] = krw_per_usdt
                self._touch_cache()
                logger.info("KRW/USDT (Frankfurter USD→KRW): %.0f KRW", krw_per_usdt)
                return krw_per_usdt
            except Exception as e2:
                logger.warning(
                    "KRW/USDT: Binance (%s), Frankfurter (%s); используем %.0f KRW",
                    e_binance,
                    e2,
                    fallback,
                )
            self.exchange_rates[key] = fallback
            self._touch_cache()
            return fallback

    def get_usdt_rub_rate(self) -> float:
        key = "usdt_rub"
        if self._rate_cached(key):
            return self.exchange_rates[key]
        try:
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTRUB", timeout=10)
            r.raise_for_status()
            rate = float(r.json()["price"])
            self.exchange_rates[key] = rate
            self._touch_cache()
            logger.info("USDT/RUB: %.2f", rate)
            return rate
        except Exception as e:
            fallback = float(self._get_price_config().get("usdt_rub") or 95.0)
            logger.warning("USDT/RUB недоступен (%s), используем %s", e, fallback)
            self.exchange_rates[key] = fallback
            self._touch_cache()
            return fallback

    def _rate_cached(self, key: str) -> bool:
        cfg = self._get_price_config()
        cache_m = float(cfg.get("cache_minutes", 5))
        return (time.time() - self.last_rate_update) < (cache_m * 60) and key in self.exchange_rates

    def _touch_cache(self) -> None:
        self.last_rate_update = time.time()

    def get_exchange_rate(self) -> float:
        """1 KRW в RUB через USDT."""
        return self.get_usdt_rub_rate() / self.get_krw_usdt_rate()

    def get_cbr_eur_rub_safe(self) -> float:
        """Курс ЦБ РФ EUR/RUB за 1 €."""
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
            logger.warning("ЦБ EUR: %s, используем 105", e)
            return self.exchange_rates.get(key, 105.0)

    def get_cbr_cny_rub_safe(self) -> float:
        """Курс ЦБ РФ CNY/RUB за 1 ¥."""
        key = "cbr_cny_rub"
        if self._rate_cached(key):
            return self.exchange_rates[key]
        try:
            r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=8)
            r.raise_for_status()
            data = r.json()
            cny = data.get("Valute", {}).get("CNY", {})
            nom = max(1, int(cny.get("Nominal", 1)))
            rate = float(cny.get("Value", 12.0)) / nom
            self.exchange_rates[key] = rate
            self._touch_cache()
            return rate
        except Exception as e:
            logger.warning("ЦБ CNY: %s, используем 12", e)
            return self.exchange_rates.get(key, 12.0)

    # --- Совместимость со старыми именами методов ---
    def calculate_customs_fee_tiered(self, car_value_rub: float) -> float:
        return customs_fee(car_value_rub)

    def calculate_customs_fee(self, price_won: float, engine_volume: int) -> float:
        return 4924.0

    def calculate_duty(self, price_won: float, age_years: int) -> float:
        return 0.0

    def calculate_utilization_fee(self, engine_volume: int) -> float:
        return UTIL_BASE_PERSONAL_RUB * 0.26

    def calculate_total_cost(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        cfg = self._get_price_config()
        documents_krw = float(cfg.get("documents_krw", DOCUMENTS_KRW))
        freight_usd = float(cfg.get("freight_usd", FREIGHT_USD))
        broker_rub = float(cfg.get("broker_rub", BROKER_RUB))
        commission_rate = float(cfg.get("commission_rate", COMMISSION_RATE_DEFAULT))

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

        krw_per_usdt = self.get_krw_usdt_rate()
        usdt_rub = self.get_usdt_rub_rate()
        krw_to_rub = usdt_rub / krw_per_usdt

        amount_krw_with_docs = price_won + documents_krw
        car_and_docs_rub = amount_krw_with_docs * krw_to_rub
        freight_rub = freight_usd * usdt_rub
        documents_krw_rub = documents_krw * krw_to_rub

        car_value_rub = car_and_docs_rub
        eur_rub = self.get_cbr_eur_rub_safe()

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
        # Для акциза используем доступную "паспортную" мощность (обычно суммарная для гибридов/EV),
        # а если её нет — fallback на мощность ДВС.
        power_for_excise = parse_power_hp(car_data)
        if power_for_excise is None:
            power_for_excise = power_ice
        excise = excise_rub(power_for_excise, excise_tiers)
        vat = vat_import_rub(car_value_rub, duty, excise, fuel=fuel, age_years=age)

        customs_total = fee + duty + excise + util + vat

        comm, comm_eff = commission_rub(car_value_rub, customs_total, broker_rub, commission_rate)
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
            "commission_rate_default": commission_rate,
            "vehicle_sum": vehicle_sum,
            "total_with_commission": total_with_commission,
            "krw_per_usdt": krw_per_usdt,
            "usdt_rub": usdt_rub,
            "eur_rub": eur_rub,
        }

    def calculate_total_cost_china(self, car_data: Dict[str, Any]) -> Dict[str, float]:
        cfg = self._get_price_config()
        docs_delivery_cny = float(cfg.get("china_docs_delivery_cny", CHINA_DOCS_DELIVERY_CNY))
        broker_rub = float(cfg.get("china_broker_rub", CHINA_BROKER_RUB))
        commission_rate = float(cfg.get("commission_rate", COMMISSION_RATE_DEFAULT))

        price_cny = parse_price_cny(car_data)
        if price_cny <= 0:
            raise ValueError("price_cny is missing or non-positive")

        cny_rub = self.get_cbr_cny_rub_safe()
        eur_rub = self.get_cbr_eur_rub_safe()
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
        excise = excise_rub(power_for_excise, excise_tiers)
        util = utilization_phys_person_rub(
            engine_cc=engine_cc,
            age_years=age,
            power_hp_ice=power_ice,
            fuel=fuel,
        )
        vat = vat_import_rub(car_value_rub, duty, excise, fuel=fuel, age_years=age)
        customs_total = fee + duty + excise + util + vat

        vehicle_sum = car_value_rub + docs_delivery_rub + customs_total + broker_rub
        commission = vehicle_sum * commission_rate
        total_with_commission = vehicle_sum + commission

        return {
            "price_cny": price_cny,
            "price_rub": car_value_rub,
            "china_docs_delivery_cny": docs_delivery_cny,
            "china_docs_delivery_rub": docs_delivery_rub,
            "customs_fee": fee,
            "duty": duty,
            "excise": excise,
            "utilization": util,
            "vat": vat,
            "customs_total": customs_total,
            "broker_rub": broker_rub,
            "commission": commission,
            "commission_rate_effective": commission_rate,
            "commission_rate_default": commission_rate,
            "vehicle_sum": vehicle_sum,
            "total_with_commission": total_with_commission,
            "cny_rub": cny_rub,
            "eur_rub": eur_rub,
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
        car_data["vehicle_sum_rub"] = prices["vehicle_sum"]
        car_data["my_price"] = prices["total_with_commission"]
        car_data["cny_rub"] = prices.get("cny_rub")
        car_data["commission_rate_effective"] = prices.get("commission_rate_effective")
        car_data["commission_rate_default"] = prices.get("commission_rate_default")
        return car_data


def main() -> None:
    calculator = PriceCalculator()
    test_car = {
        "price_won": 3000,
        "displacement": 2000,
        "year": 2019,
        "engine_type": "가솔린",
        "power": "184",
    }
    p = calculator.calculate_total_cost(test_car)
    print("Пример расчёта:")
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
