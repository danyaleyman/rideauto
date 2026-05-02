#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Общая часть для рынков: классификация ДВС, таблицы ввоза физлица в РФ, официальные курсы ЦБ РФ.
Криптобиржи и сторонние FX API не используются для продакшен-расчёта ₽/$ и ₽/₩.
Корейский след: если в котировках ЦБ нет KRW — кросс «USD ЦБ × ₩/$» с явным параметром из config (price.krw_per_usd).
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
EXCISE_HP_TIERS_RUB_PER_HP: List[Tuple[float, float]] = [
    (90.0, 0.0),
    (150.0, 64.0),
    (200.0, 613.0),
    (300.0, 1004.0),
    (400.0, 1711.0),
    (500.0, 1771.0),
    (float("inf"), 1829.0),
]
# НДС при импорте (база: таможенная стоимость + пошлина + акциз), ориентир для калькулятора физлица.
VAT_IMPORT_RATE = 0.20


def _util_age_band(age_years: int) -> str:
    if age_years < 3:
        return "0-3"
    if age_years <= 5:
        return "3-5"
    return "5+"


def _effective_power_util(
    eng_type: str,
    hybrid_type: str,
    hp_ice: float,
    hp_ed_peak: float,
) -> float:
    """Совпадает с BuyCalculator.effectivePowerHp (30-мин. мощность ЭД = 0.45×пик)."""
    ed30 = hp_ed_peak * 0.45
    if eng_type == "electric":
        return ed30
    if eng_type == "hybrid":
        return ed30 if hybrid_type == "series" else hp_ice + ed30
    return hp_ice


def utilization_buy_page_rub(
    *,
    age: str,
    eng_type: str,
    hybrid_type: str,
    vol: int,
    hp_ice: float,
    hp_ed: float,
    purpose: str,
) -> float:
    """Паритет с web/src/components/buy/BuyCalculator.tsx → getUtil."""
    base = UTIL_BASE_PERSONAL_RUB
    is_personal = purpose == "personal"
    effective_power = _effective_power_util(eng_type, hybrid_type, hp_ice, hp_ed)

    if is_personal:
        if eng_type == "electric" or (eng_type == "hybrid" and hybrid_type == "series"):
            is_loyal = effective_power <= 80
        else:
            is_loyal = effective_power <= 160
        if is_loyal:
            return 3400.0 if age == "0-3" else 5200.0

    if (eng_type == "electric" or (eng_type == "hybrid" and hybrid_type == "series")) and effective_power > 80:
        coeff = 1.0
        if age == "0-3":
            if effective_power <= 100:
                coeff = 65.88
            elif effective_power <= 130:
                coeff = 79.2
            elif effective_power <= 160:
                coeff = 93.6
            else:
                coeff = 110.4
        elif age == "3-5":
            if effective_power <= 100:
                coeff = 151.2
            elif effective_power <= 130:
                coeff = 172.8
            elif effective_power <= 160:
                coeff = 201.6
            else:
                coeff = 240.0
        else:
            if effective_power <= 100:
                coeff = 240.0
            elif effective_power <= 130:
                coeff = 280.0
            elif effective_power <= 160:
                coeff = 320.0
            else:
                coeff = 360.0
        return float(round(base * coeff))

    power_kw = effective_power * 0.7355
    coeff = 1.0
    if age == "0-3":
        if vol <= 1000:
            if power_kw <= 50:
                coeff = 1.63
            elif power_kw <= 100:
                coeff = 1.85
            else:
                coeff = 2.08
        elif vol <= 2000:
            if effective_power > 160:
                coeff = 45.0
            elif power_kw <= 100:
                coeff = 3.01
            elif power_kw <= 150:
                coeff = 3.62
            else:
                coeff = 4.23
        elif vol <= 3000:
            coeff = 120.12 if eng_type == "diesel" else 118.2
        elif vol <= 3500:
            if power_kw <= 200:
                coeff = 9.23
            elif power_kw <= 220:
                coeff = 10.05
            else:
                coeff = 144.0
        else:
            coeff = 12.29
    elif age == "3-5":
        if vol <= 1000:
            coeff = 5.73
        elif vol <= 2000:
            if power_kw > 161.8:
                coeff = 177.6
            elif power_kw > 117.7:
                coeff = 74.64
            else:
                coeff = 8.95
        elif vol <= 3000:
            if power_kw > 161.8:
                coeff = 177.6
            elif power_kw > 117.7:
                coeff = 74.64
            else:
                coeff = 32.0
        elif vol <= 3500:
            coeff = 45.0
        else:
            coeff = 60.0
    else:
        if vol <= 1000:
            coeff = 17.5
        elif vol <= 2000:
            if power_kw > 161.8:
                coeff = 177.6
            elif power_kw > 117.7:
                coeff = 74.64
            else:
                coeff = 28.5
        elif vol <= 3000:
            if power_kw > 161.8:
                coeff = 177.6
            elif power_kw > 117.7:
                coeff = 74.64
            else:
                coeff = 85.0
        elif vol <= 3500:
            coeff = 120.0
        else:
            coeff = 150.0

    return float(round(base * coeff))


def _engine_type_is_diesel(car_data: Dict[str, Any]) -> bool:
    raw = str(car_data.get("engine_type") or "")
    lo = raw.lower()
    return "дизель" in lo or "diesel" in lo or "디젤" in raw


def _hybrid_series_hint(car_data: Dict[str, Any]) -> bool:
    s = str(car_data.get("hybrid_layout") or car_data.get("hybrid_type") or "").strip().lower()
    return s in ("series", "serial", "последовательный", "series_hybrid")


def _hybrid_ed_peak_hp(car_data: Dict[str, Any]) -> float:
    for key in ("power_electric_hp", "electric_motor_hp", "motor_hp_peak"):
        v = car_data.get(key)
        if v is not None and v != "":
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    kw = car_data.get("electric_motor_kw") or car_data.get("motor_kw_peak")
    if kw is not None and kw != "":
        try:
            return float(kw) / 0.7355
        except (TypeError, ValueError):
            pass
    return 0.0


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
    car_data: Optional[Dict[str, Any]] = None,
) -> float:
    """Утилизационный сбор физлица — та же логика, что BuyCalculator.getUtil (страница «Как купить»)."""
    cd = car_data if isinstance(car_data, dict) else {}
    age = _util_age_band(age_years)
    hp_i = float(power_hp_ice or 0)
    vol = int(engine_cc)
    if vol <= 0:
        vol = 2000

    if fuel == "electric":
        peak = hp_i
        if peak <= 0:
            ph = parse_power_hp(cd)
            peak = float(ph or 0)
        return utilization_buy_page_rub(
            age=age,
            eng_type="electric",
            hybrid_type="none",
            vol=0,
            hp_ice=0.0,
            hp_ed=peak,
            purpose="personal",
        )

    if fuel == "hybrid":
        series = _hybrid_series_hint(cd)
        hp_ed = _hybrid_ed_peak_hp(cd)
        return utilization_buy_page_rub(
            age=age,
            eng_type="hybrid",
            hybrid_type="series" if series else "parallel",
            vol=vol,
            hp_ice=hp_i,
            hp_ed=hp_ed,
            purpose="personal",
        )

    eng = "diesel" if _engine_type_is_diesel(cd) else "petrol"
    return utilization_buy_page_rub(
        age=age,
        eng_type=eng,
        hybrid_type="none",
        vol=vol,
        hp_ice=hp_i,
        hp_ed=0.0,
        purpose="personal",
    )


def excise_rub(power_hp: Optional[float], hp_tiers: Optional[List[Tuple[float, float]]] = None) -> float:
    """Акциз на автомобили: ₽ за каждую л.с. в интервале (ступени по верхней границе мощности, см. НК РФ)."""
    if power_hp is None or power_hp <= 0:
        return 0.0
    tiers = hp_tiers if hp_tiers is not None else EXCISE_HP_TIERS_RUB_PER_HP
    if not tiers:
        return 0.0
    p = float(power_hp)
    total = 0.0
    prev_top = 0.0
    for cap_raw, rub_per_hp in tiers:
        cap = float(cap_raw)
        if p <= prev_top:
            break
        segment_hi = min(p, cap)
        width = max(0.0, segment_hi - prev_top)
        total += width * float(rub_per_hp)
        prev_top = cap
        if segment_hi >= p:
            break
    return float(round(total, 2))


def vat_import_rub(
    car_value_rub: float,
    duty_rub: float,
    excise_value_rub: float,
    *,
    fuel: str,
    age_years: int,
) -> float:
    _ = fuel, age_years
    base = (
        max(0.0, float(car_value_rub))
        + max(0.0, float(duty_rub))
        + max(0.0, float(excise_value_rub))
    )
    return float(round(base * VAT_IMPORT_RATE, 2))


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
    """Официальные курсы ЦБ РФ (кеш) + параметры конфига на случай недоступности выгрузки."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config: Dict[str, Any] = _load_json_config(config_path)
        self.exchange_rates: Dict[str, float] = {}
        self.last_rate_update = 0.0
        self._cbr_valutes_snapshot: Optional[Dict[str, Any]] = None
        self._cbr_valutes_snapshot_at: float = 0.0
        # Один INFO на прогон каталога, а не на каждую строку (resolve_korea_krw_to_rub).
        self._info_logged_krw_direct = False
        self._info_logged_krw_cross = False

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

    def _get_cbr_valutes_dict(self) -> Dict[str, Any]:
        ttl = self._cache_ttl_sec()
        if (
            isinstance(self._cbr_valutes_snapshot, dict)
            and self._cbr_valutes_snapshot
            and (time.time() - self._cbr_valutes_snapshot_at) < ttl
        ):
            return self._cbr_valutes_snapshot
        last_err: Optional[Exception] = None
        for url in (
            "https://www.cbr-xml-daily.ru/daily_json.js",
            "https://www.cbr-xml-daily.ru/latest.js",
        ):
            try:
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                vu = r.json().get("Valute")
                snap = vu if isinstance(vu, dict) else {}
                self._cbr_valutes_snapshot = snap
                self._cbr_valutes_snapshot_at = time.time()
                self._touch_cache()
                return snap
            except Exception as e:
                last_err = e
        logger.warning("ЦБ JSON (Valute): %s", last_err)
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

    def get_cbr_krw_rub_per_won_optional(self) -> Optional[float]:
        vu = self._get_cbr_valutes_dict()
        rate = _cbr_rub_per_one_foreign_unit(vu.get("KRW"))
        return rate if rate is not None and rate > 0 else None

    def get_cbr_usd_rub_exclusive(self) -> float:
        """
        Только официальный курс USD ЦБ ₽/$ (ключ price.usd_rub или price.usdt_rub только как запас,
        когда выгрузка ЦБ временно недоступна — не биржа).
        """
        if self._rate_cached("usd_rub_cbr"):
            return float(self.exchange_rates["usd_rub_cbr"])
        vu = self._get_cbr_valutes_dict()
        rate = _cbr_rub_per_one_foreign_unit(vu.get("USD")) if vu else None
        if rate is not None and rate > 0:
            self.exchange_rates["usd_rub_cbr"] = rate
            self.exchange_rates["usdt_rub"] = rate
            self._touch_cache()
            logger.info("ЦБ USD/RUB: %.4f ₽ за 1 USD", rate)
            return rate
        cfg = self._price_cfg()
        fb = float(cfg.get("usd_rub") or cfg.get("usdt_rub") or 95.0)
        logger.warning("Курс USD ЦБ временно недоступен — из конфига price.usd_rub / usdt_rub: %.4f", fb)
        self.exchange_rates["usd_rub_cbr"] = fb
        self.exchange_rates["usdt_rub"] = fb
        self._touch_cache()
        return fb

    def get_cbr_usd_rub_safe(self) -> float:
        """Совместимость: синоним `get_cbr_usd_rub_exclusive`."""
        return self.get_cbr_usd_rub_exclusive()

    def get_usdt_rub_rate(self) -> float:
        """Обратная совместимость полей объявления: фактически официальный USD ЦБ, не Binance/USDT."""
        return self.get_cbr_usd_rub_exclusive()

    def get_approx_krw_per_usd(self) -> float:
        """
        Сколько корейских вон за 1 USD — только из конфига, если прямого KRW в Valute ЦБ нет.
        Поля по приоритету: price.krw_per_usd, price.krw_per_usd_approx, price.krw_per_usd_fallback.
        """
        if self._rate_cached("approx_kpw_per_usd"):
            return float(self.exchange_rates["approx_kpw_per_usd"])
        cfg = self._price_cfg()
        parsed: Optional[float] = None
        for kname in ("krw_per_usd", "krw_per_usd_approx"):
            raw = cfg.get(kname)
            if raw is None or raw == "":
                continue
            try:
                v = float(raw)
                if v > 0:
                    parsed = v
                    logger.warning(
                        "В котировках ЦБ нет KRW или он не загрузился — для кросса к USD используем конфиг "
                        "%s = %.4f ₩/$ (задайте price.krw_per_usd актуально).",
                        kname,
                        v,
                    )
                    break
            except (TypeError, ValueError):
                continue
        if parsed is None:
            try:
                parsed = float(cfg.get("krw_per_usd_fallback") or 1470.0)
            except (TypeError, ValueError):
                parsed = 1470.0
            logger.warning(
                "ЦБ KRW недоступен и price.krw_per_usd не задан — временно ₩/$ = %.4f (fallback).",
                parsed,
            )
        self.exchange_rates["approx_kpw_per_usd"] = parsed
        self._touch_cache()
        return parsed

    def resolve_korea_krw_to_rub(self) -> Tuple[float, str]:
        """
        Сколько ₽ за одну южнокорейскую вону: прямо из строки Valute[KRW],
        либо (USD ЦБ) / (₩/$ из конфига).
        """
        direct = self.get_cbr_krw_rub_per_won_optional()
        if direct is not None and direct > 0:
            if not self._info_logged_krw_direct:
                self._info_logged_krw_direct = True
                logger.info("ЦБ KRW/RUB: %.6f ₽ за 1 KRW", direct)
            return float(direct), "cbr_krw_direct"

        usd_rub = self.get_cbr_usd_rub_exclusive()
        kpw = self.get_approx_krw_per_usd()
        rp = float(usd_rub) / max(kpw, 1e-9)
        if not self._info_logged_krw_cross:
            self._info_logged_krw_cross = True
            logger.info(
                "Модель ₽/₩ через USD ЦБ: %.6f = %.4f (₽/$) ÷ %.2f (₩/$ конфиг)",
                rp,
                usd_rub,
                kpw,
            )
        return rp, "cbr_usd_cross_config_kpw"

    def get_krw_usdt_rate(self) -> float:
        """Совместимость: трактовать как ₩ за 1 USD для старых цепочек (без биржевого оркакула)."""
        return float(self.get_approx_krw_per_usd())

    def get_exchange_rate(self) -> float:
        """Приблизительно 1 KRW → RUB только по правилам `resolve_korea_krw_to_rub`."""
        return float(self.resolve_korea_krw_to_rub()[0])
