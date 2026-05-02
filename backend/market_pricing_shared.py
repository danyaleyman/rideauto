#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Общая часть для рынков: классификация ДВС, таблицы ввоза физлица в РФ, курсы (ЦБ + Binance).
Не импортировать код «Корея» из «Китай» и наоборот — здесь только нейтральные расчёты.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

logger = logging.getLogger(__name__)

# --- Общая шкала комиссии (страховалка одинакового подхода; порог задаётся в ₽ до полной суммы таможни) ---
COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB: Tuple[Tuple[float, float], ...] = (
    (1_500_000.0, 150_000.0),
    (3_000_000.0, 230_000.0),
    (7_000_000.0, 300_000.0),
    (float("inf"), 400_000.0),
)
COMMISSION_RATE_DEFAULT = 0.0

UTIL_BASE_PERSONAL_RUB = 20_000
DUTY_EUR_PER_CC_3_5: Tuple[float, ...] = (1.5, 1.7, 2.5, 2.7, 3.0, 3.6)
DUTY_EUR_PER_CC_5_PLUS: Tuple[float, ...] = (3.0, 3.2, 3.5, 4.8, 5.0, 5.7)
DUTY_UNDER3_EUR_TIERS: List[Tuple[float, float, float]] = [
    (8500.0, 0.54, 2.5),
    (16700.0, 0.48, 3.5),
    (42300.0, 0.48, 5.5),
    (84500.0, 0.48, 7.5),
    (169000.0, 0.48, 15.0),
    (float("inf"), 0.48, 20.0),
]
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
UTIL_HP_THRESHOLD = 160
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
EXCISE_HP_TIERS_RUB_PER_HP: List[Tuple[float, float]] = [
    (90.0, 0.0),
    (150.0, 64.0),
    (200.0, 613.0),
    (300.0, 1004.0),
    (400.0, 1711.0),
    (500.0, 1771.0),
    (float("inf"), 1829.0),
]
UTIL_POWER_MULTIPLIER_TIERS: List[Tuple[float, float]] = [
    (160.0, 1.0),
    (200.0, 1.1),
    (250.0, 1.25),
    (300.0, 1.45),
    (float("inf"), 1.7),
]


def engine_volume_bracket_index(engine_cc: int) -> int:
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
        if iv < 100 and "." not in up:
            return iv * 100
        return iv
    except (TypeError, ValueError):
        return 0


def customs_fee(car_value_rub: float) -> float:
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
    _ = car_value_rub, duty_rub, excise_value_rub, fuel, age_years
    return 0.0


def _cbr_rub_per_one_foreign_unit(valute_entry: Any) -> Optional[float]:
    if not isinstance(valute_entry, dict):
        return None
    try:
        nom = max(1, int(valute_entry.get("Nominal") or 1))
        val = float(valute_entry.get("Value") or 0)
        if val <= 0:
            return None
        return val / float(nom)
    except (TypeError, ValueError):
        return None


def parse_commission_schedule_from_config(raw: Any) -> List[Tuple[float, float]]:
    if not isinstance(raw, list) or not raw:
        return list(COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB)
    out: List[Tuple[float, float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        lim_raw, amt_raw = item[0], item[1]
        try:
            amt = float(amt_raw)
        except (TypeError, ValueError):
            continue
        if lim_raw in (None, "", False, "inf"):
            out.append((float("inf"), amt))
        else:
            try:
                lim = float(lim_raw)
            except (TypeError, ValueError):
                continue
            out.append((lim, amt))
    if not out:
        return list(COMMISSION_SCHEDULE_CAR_THRESHOLD_RUB)
    out.sort(key=lambda x: x[0])
    return out


def commission_rub_tiered(
    car_value_rub_for_tiers: float,
    customs_total_rub: float,
    broker_rub: float,
    schedule: Sequence[Tuple[float, float]],
) -> Tuple[float, float]:
    anchor = car_value_rub_for_tiers + customs_total_rub + broker_rub
    comm = float(schedule[-1][1]) if schedule else 0.0
    for limit, amount in schedule:
        if car_value_rub_for_tiers <= limit:
            comm = float(amount)
            break
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


def _load_json_config(config_path: str) -> Dict[str, Any]:
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Конфиг не найден: %s, умолчания", config_path)
        return {}
    except json.JSONDecodeError:
        return {}


class PricingFxRates:
    """Кэш курсов Бинанс + ЦБ (используется калькуляторами рынков)."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config: Dict[str, Any] = _load_json_config(config_path)
        self.exchange_rates: Dict[str, float] = {}
        self.last_rate_update = 0.0
        self._cbr_valutes_snapshot: Optional[Dict[str, Any]] = None
        self._cbr_valutes_snapshot_at: float = 0.0

    def _price_cfg(self) -> Dict[str, Any]:
        p = self.config.get("price")
        return p if isinstance(p, dict) else {}

    def _rate_cached(self, key: str) -> bool:
        cache_m = float(self._price_cfg().get("cache_minutes", 5))
        return (time.time() - self.last_rate_update) < (cache_m * 60) and key in self.exchange_rates

    def _touch_cache(self) -> None:
        self.last_rate_update = time.time()

    def _cache_ttl_sec(self) -> float:
        return float(self._price_cfg().get("cache_minutes", 5)) * 60.0

    def get_krw_usdt_rate(self) -> float:
        key = "krw_per_usdt"
        if self._rate_cached(key):
            return self.exchange_rates[key]
        cfg = self._price_cfg()
        fallback = float(cfg.get("krw_per_usdt") or cfg.get("krw_per_usdt_fallback") or 1400.0)
        try:
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
            fallback = float(self._price_cfg().get("usdt_rub") or 95.0)
            logger.warning("USDT/RUB недоступен (%s), используем %s", e, fallback)
            self.exchange_rates[key] = fallback
            self._touch_cache()
            return fallback

    def get_exchange_rate(self) -> float:
        return self.get_usdt_rub_rate() / self.get_krw_usdt_rate()

    def _get_cbr_valutes_dict(self) -> Dict[str, Any]:
        ttl = self._cache_ttl_sec()
        if (
            isinstance(self._cbr_valutes_snapshot, dict)
            and self._cbr_valutes_snapshot
            and (time.time() - self._cbr_valutes_snapshot_at) < ttl
        ):
            return self._cbr_valutes_snapshot
        try:
            r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=8)
            r.raise_for_status()
            vu = r.json().get("Valute")
            snap = vu if isinstance(vu, dict) else {}
            self._cbr_valutes_snapshot = snap
            self._cbr_valutes_snapshot_at = time.time()
            self._touch_cache()
            return snap
        except Exception as e:
            logger.warning("ЦБ JSON (Valute): %s", e)
            if isinstance(self._cbr_valutes_snapshot, dict):
                return self._cbr_valutes_snapshot
            return {}

    def _cbr_currency_rub(self, code: str, fallback: float, *, snapshot: Optional[Dict[str, Any]] = None) -> float:
        key = f"cbr_{code.lower()}_rub"
        vu = snapshot if snapshot is not None else self._get_cbr_valutes_dict()
        rate = _cbr_rub_per_one_foreign_unit(vu.get(code)) if vu else None
        if rate is not None and rate > 0:
            self.exchange_rates[key] = rate
            self._touch_cache()
            return rate
        if key in self.exchange_rates and float(self.exchange_rates[key]) > 0:
            return float(self.exchange_rates[key])
        self.exchange_rates[key] = fallback
        self._touch_cache()
        return fallback

    def get_cbr_eur_rub_safe(self) -> float:
        return self._cbr_currency_rub("EUR", 105.0)

    def get_cbr_cny_rub_safe(self) -> float:
        return self._cbr_currency_rub("CNY", 12.0)

    def get_cbr_usd_rub_safe(self) -> float:
        vu = self._get_cbr_valutes_dict()
        direct = _cbr_rub_per_one_foreign_unit(vu.get("USD")) if vu else None
        if direct is not None and direct > 0:
            self.exchange_rates["cbr_usd_rub"] = direct
            self._touch_cache()
            return direct
        usdt_fb = float(self._price_cfg().get("usdt_rub") or 95.0)
        try:
            alt = float(self.get_usdt_rub_rate())
            if alt > 0:
                self.exchange_rates["cbr_usd_rub"] = alt
                return alt
        except Exception:
            pass
        return usdt_fb

    def get_cbr_krw_rub_per_won_optional(self) -> Optional[float]:
        vu = self._get_cbr_valutes_dict()
        rate = _cbr_rub_per_one_foreign_unit(vu.get("KRW"))
        return rate if rate is not None and rate > 0 else None
