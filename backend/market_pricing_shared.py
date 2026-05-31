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
import re
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
# НДС при импорте (база: таможенная стоимость + пошлина + акциз).
VAT_IMPORT_RATE = 0.20
# СТП для EV (8703 80): адвалорная пошлина в составе совокупного платежа, ЕЭК №107 табл. 2 п. 4.
EV_PHYS_STP_DUTY_ADVALOREM_RATE = 0.15

# Утиль: ПП №1291 (ред. ПП №1713), индексация коэффициентов с 01.01.2026 (база 20 000 ₽).
_UtilHpBand = Tuple[Tuple[float, float], ...]
ICE_UTIL_POWER_COEFF_0_3: _UtilHpBand = (
    (160.0, 40.04),
    (190.0, 45.0),
    (220.0, 47.64),
    (250.0, 50.52),
    (280.0, 57.12),
    (310.0, 64.56),
    (340.0, 72.96),
    (float("inf"), 72.96),
)
ICE_UTIL_POWER_COEFF_OLDER: _UtilHpBand = (
    (160.0, 70.44),
    (190.0, 74.64),
    (220.0, 79.2),
    (250.0, 83.88),
    (280.0, 91.92),
    (310.0, 100.56),
    (340.0, 110.16),
    (float("inf"), 110.16),
)
EV_UTIL_POWER_COEFF_0_3: _UtilHpBand = (
    (100.0, 49.56),
    (130.0, 65.88),
    (160.0, 78.0),
    (190.0, 92.4),
    (220.0, 109.68),
    (250.0, 129.96),
    (280.0, 153.96),
    (float("inf"), 153.96),
)
EV_UTIL_POWER_COEFF_OLDER: _UtilHpBand = (
    (100.0, 82.08),
    (130.0, 95.64),
    (160.0, 111.36),
    (190.0, 129.72),
    (220.0, 151.2),
    (250.0, 176.16),
    (float("inf"), 176.16),
)


def _util_age_band(age_years: int) -> str:
    if age_years < 3:
        return "0-3"
    if age_years <= 5:
        return "3-5"
    return "5+"


def _util_coeff_by_power(hp: float, bands: _UtilHpBand) -> float:
    p = max(0.0, float(hp))
    for cap, coeff in bands:
        if p <= cap:
            return float(coeff)
    return float(bands[-1][1])


def _util_ice_power_coeff(age: str, effective_hp: float) -> float:
    bands = ICE_UTIL_POWER_COEFF_0_3 if age == "0-3" else ICE_UTIL_POWER_COEFF_OLDER
    return _util_coeff_by_power(effective_hp, bands)


def _util_ev_power_coeff(age: str, effective_hp: float) -> float:
    bands = EV_UTIL_POWER_COEFF_0_3 if age == "0-3" else EV_UTIL_POWER_COEFF_OLDER
    return _util_coeff_by_power(effective_hp, bands)


# 30-минутная (рабочая) мощность электромотора ≈ 0.45 × пик (ЕЭК / практика TKS).
ED_THIRTY_MIN_HP_FACTOR = 0.45


def _ed_thirty_min_hp(hp_ed_peak: float) -> float:
    return max(0.0, float(hp_ed_peak)) * ED_THIRTY_MIN_HP_FACTOR


def _effective_power_util(
    eng_type: str,
    hybrid_type: str,
    hp_ice: float,
    hp_ed_peak: float,
) -> float:
    """
    Мощность для утиля/таможни:
    - ДВС: пик ДВС;
    - EV: 30-мин. мощность ЭД;
    - parallel HEV/PHEV: пик ДВС + пик ЭД (полная сумма);
    - series HEV: только 30-мин. мощность ЭД (ДВС — генератор).
    """
    ed30 = _ed_thirty_min_hp(hp_ed_peak)
    if eng_type == "electric":
        return ed30
    if eng_type == "hybrid":
        return ed30 if hybrid_type == "series" else hp_ice + max(0.0, float(hp_ed_peak))
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

    if eng_type == "electric" or (eng_type == "hybrid" and hybrid_type == "series"):
        if effective_power > 80 or not is_personal:
            coeff = _util_ev_power_coeff(age, effective_power)
            return float(round(base * coeff))

    if effective_power > 160:
        coeff = _util_ice_power_coeff(age, effective_power)
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
    try:
        from hybrid_power import infer_hybrid_layout

        return infer_hybrid_layout(car_data) == "series"
    except ImportError:
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
    chunks: List[str] = []
    for key in ("engine_type", "engine_type_original", "engine_type_ru", "fuel", "engineType"):
        v = car_data.get(key)
        if v not in (None, ""):
            chunks.append(str(v))
    raw = " ".join(chunks)
    s = raw.lower()
    ko = raw

    if "전기" in ko and "가솔린" not in ko and "디젤" not in ko and "하이브리드" not in ko:
        if "+" not in ko and "электр" not in s and "+" not in raw:
            return "electric"
    if ("electric" in s or s.strip() == "ev" or "электро" in s) and "+" not in raw:
        if not any(x in s for x in ("hybrid", "гибрид", "hev", "phev")) and "бензин" not in s and "дизель" not in s:
            if "электричество" not in s:
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
        or ("бензин" in s and ("электр" in s or "электричество" in s))
        or ("дизель" in s and ("электр" in s or "электричество" in s))
        or ("gasoline" in s and "electric" in s)
        or ("diesel" in s and "electric" in s)
        or ("gas" in s and "electric" in s and "+" in raw)
    ):
        return "hybrid"

    return "ice"


def _enrich_hybrid_power_if_needed(car_data: Dict[str, Any], fuel: str) -> None:
    if fuel != "hybrid" or not isinstance(car_data, dict):
        return
    try:
        from hybrid_power import enrich_hybrid_power_fields

        enrich_hybrid_power_fields(car_data)
    except ImportError:
        pass


def ice_engine_inputs(car_data: Dict[str, Any], fuel: str) -> Tuple[int, Optional[float]]:
    disp = (
        car_data.get("engine_volume")
        or car_data.get("displacement")
        or car_data.get("displacement_cc")
        or car_data.get("displacement_label")
        or car_data.get("che168_displacement_label")
    )
    engine_cc = parse_engine_cc(disp)

    if fuel == "electric":
        return 0, None

    _enrich_hybrid_power_if_needed(car_data, fuel)

    hp: Optional[float] = None
    if fuel == "hybrid" and car_data.get("power_ice_hp") is not None:
        try:
            hp = float(car_data["power_ice_hp"])
        except (TypeError, ValueError):
            hp = None
    if hp is None:
        hp = parse_power_hp(car_data)

    return engine_cc, hp


def parse_power_hp(car_data: Dict[str, Any]) -> Optional[float]:
    if isinstance(car_data, dict) and str(car_data.get("source") or "").strip().lower() == "che168":
        try:
            from scraper_pipeline.che168.parser import resolve_che168_power_hp

            raw = car_data.get("che168_params_raw")
            engine = str(car_data.get("engine") or "")
            if raw is not None:
                hp = resolve_che168_power_hp(raw, engine)
                if hp is not None and hp > 0:
                    return float(hp)
        except ImportError:
            pass

    fuel = classify_fuel(car_data) if isinstance(car_data, dict) else "ice"
    if fuel == "hybrid" and isinstance(car_data, dict):
        _enrich_hybrid_power_if_needed(car_data, fuel)
        for key in ("power_hp", "power", "power_hp_system"):
            v = car_data.get(key)
            if v not in (None, ""):
                try:
                    n = float(re.sub(r"[^\d.]", "", str(v)) or "0")
                    if n > 0:
                        return n
                except (TypeError, ValueError):
                    pass
        comp_ice = car_data.get("power_ice_hp")
        comp_ed = car_data.get("power_electric_hp")
        if comp_ice is not None and comp_ed is not None:
            try:
                return float(comp_ice) + float(comp_ed)
            except (TypeError, ValueError):
                pass

    p = (
        car_data.get("power")
        or car_data.get("power_hp")
        or car_data.get("hp")
        or car_data.get("outputHorsepower")
    )
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
        return float(round(max(0.0, car_value_rub) * EV_PHYS_STP_DUTY_ADVALOREM_RATE, 2))

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
        _enrich_hybrid_power_if_needed(cd, fuel)
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


def _parse_excise_tiers(raw: Any) -> Optional[List[Tuple[float, float]]]:
    if not isinstance(raw, list):
        return None
    parsed: List[Tuple[float, float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        try:
            parsed.append((float(item[0]), float(item[1])))
        except (TypeError, ValueError):
            continue
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    return parsed


def phys_person_import_charges(
    *,
    car_value_rub: float,
    eur_rub: float,
    engine_cc: int,
    age_years: int,
    fuel: str,
    car_data: Optional[Dict[str, Any]] = None,
    excise_hp_tiers: Optional[Any] = None,
) -> Dict[str, float]:
    """
    Таможня РФ для физлица (личное пользование).
    ДВС/гибрид: единая ставка (пошлина) + сбор + утиль; акциз/НДС отдельно не начисляются.
    EV: СТП = пошлина 15% + акциз + НДС (ЕЭК №107, п. 4 табл. 2).
    """
    cd = car_data if isinstance(car_data, dict) else {}
    tiers = _parse_excise_tiers(excise_hp_tiers)

    _cc, power_ice = ice_engine_inputs(cd, fuel)
    vol = int(engine_cc) if engine_cc > 0 else int(_cc)

    fee = customs_fee(car_value_rub)
    util = utilization_phys_person_rub(
        engine_cc=vol,
        age_years=age_years,
        power_hp_ice=power_ice,
        fuel=fuel,
        car_data=cd,
    )
    duty = duty_phys_person_rub(
        car_value_rub=car_value_rub,
        eur_rub=eur_rub,
        engine_cc=vol,
        age_years=age_years,
        fuel=fuel,
    )

    if fuel == "electric":
        peak = parse_power_hp(cd)
        excise_hp = _ed_thirty_min_hp(float(peak or 0))
        excise = excise_rub(excise_hp if excise_hp > 0 else None, tiers)
        vat = vat_import_rub(car_value_rub, duty, excise, fuel=fuel, age_years=age_years)
    else:
        excise = 0.0
        vat = 0.0

    customs_total = fee + duty + excise + util + vat
    return {
        "customs_fee": fee,
        "duty": duty,
        "excise": excise,
        "utilization": util,
        "vat": vat,
        "customs_total": customs_total,
    }


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
    try:
        from catalog_pg_core import parse_registration_ym_from_data

        ym = parse_registration_ym_from_data(car_data if isinstance(car_data, dict) else {})
        if ym is not None:
            return int(ym // 100)
    except ImportError:
        pass
    y = car_data.get("year") or car_data.get("Year") or datetime.now().year - 5
    if isinstance(y, str):
        digits = "".join(c for c in y if c.isdigit())
        y = int(digits[:4]) if len(digits) >= 4 else datetime.now().year - 5
    return int(y)


def age_years_car(year: int) -> int:
    return max(0, datetime.now().year - year)


def age_years_for_customs(car_data: Dict[str, Any]) -> int:
    """Возраст для пошлины/утиля: по месяцу первичной регистрации, если известен."""
    try:
        from catalog_pg_core import parse_registration_ym_from_data

        ym = parse_registration_ym_from_data(car_data if isinstance(car_data, dict) else {})
        if ym is not None:
            now = datetime.now()
            now_m = now.year * 12 + (now.month - 1)
            car_m = (ym // 100) * 12 + (ym % 100 - 1)
            age_months = max(0, now_m - car_m)
            return age_months // 12
    except ImportError:
        pass
    return age_years_car(parse_year(car_data))


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
