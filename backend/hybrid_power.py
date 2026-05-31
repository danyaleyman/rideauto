# -*- coding: utf-8 -*-
"""
Мощность гибридов: ДВС + электромотор + системная (витрина) и поля для таможни/утиля.

Encar и hp_catalog чаще отдают только л.с. ДВС; для parallel HEV нужны
power_ice_hp, power_electric_hp и power_hp (системная) отдельно.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DATA_PATH = Path(__file__).resolve().parent / "data" / "hybrid_power_specs.json"
_DATA_FALLBACK = Path(__file__).resolve().parent.parent / "data" / "hybrid_power_specs.json"


def _specs_file() -> Path:
    if _DATA_PATH.exists():
        return _DATA_PATH
    return _DATA_FALLBACK

_HP_IN_TEXT = re.compile(
    r"(\d{2,4}(?:[.,]\d{1,2})?)\s*(?:"
    r"hp|ps|л\.?\s*с\.?|л\.с|마력|马力|匹"
    r"|kW|кВт|kw"
    r")\b",
    re.IGNORECASE,
)
_KW_HINT = re.compile(r"kW|кВт|kw", re.IGNORECASE)


def _norm_ws(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip())


def _parse_hp_value(raw: Any) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        s = str(raw).strip().replace(",", ".")
        n = float(re.sub(r"[^\d.]", "", s) or "0")
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    if isinstance(raw, str) and _KW_HINT.search(raw) and 5 <= n <= 600:
        n = n / 0.7355
    elif isinstance(raw, (int, float)) and isinstance(raw, float) and raw != int(raw) and 5 <= n <= 600:
        n = n / 0.7355
    if 10 <= n <= 2500:
        return float(n)
    return None


def _car_cc(car_data: Dict[str, Any]) -> Optional[int]:
    for key in ("displacement_cc", "displacement", "engine_volume"):
        v = car_data.get(key)
        if v in (None, ""):
            continue
        try:
            n = int(re.sub(r"\D", "", str(v)) or "0")
            if 500 <= n <= 8000:
                return n
        except (TypeError, ValueError):
            continue
    return None


def _ice_hp_from_car(car_data: Dict[str, Any]) -> Optional[float]:
    for key in ("power_ice_hp", "power_kwhp", "power"):
        v = car_data.get(key)
        hp = _parse_hp_value(v)
        if hp is not None:
            return hp
    for key in ("power_hp", "hp", "outputHorsepower"):
        if car_data.get("power_ice_hp") not in (None, ""):
            break
        hp = _parse_hp_value(car_data.get(key))
        if hp is not None:
            return hp
    return None


def _electric_hp_from_car(car_data: Dict[str, Any]) -> Optional[float]:
    for key in (
        "power_electric_hp",
        "electric_motor_hp",
        "motor_hp_peak",
        "power_otherp",
        "power_kwh",
    ):
        hp = _parse_hp_value(car_data.get(key))
        if hp is not None:
            return hp
    kw = car_data.get("electric_motor_kw") or car_data.get("motor_kw_peak")
    if kw not in (None, ""):
        try:
            return float(kw) / 0.7355
        except (TypeError, ValueError):
            pass
    return None


def _iter_nested_strings(obj: Any, depth: int = 0) -> List[str]:
    if depth > 8:
        return []
    out: List[str] = []
    if isinstance(obj, str):
        t = obj.strip()
        if t:
            out.append(t)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k).lower()
            if any(
                x in ks
                for x in (
                    "motor",
                    "electric",
                    "hybrid",
                    "power",
                    "출력",
                    "모터",
                    "전기",
                    "마력",
                    "hp",
                    "kw",
                )
            ):
                out.extend(_iter_nested_strings(v, depth + 1))
            elif depth < 3:
                out.extend(_iter_nested_strings(v, depth + 1))
    elif isinstance(obj, list):
        for item in obj[:80]:
            out.extend(_iter_nested_strings(item, depth + 1))
    return out


def _scan_texts_for_hp(texts: List[str]) -> List[float]:
    found: List[float] = []
    for text in texts:
        if not text:
            continue
        for m in _HP_IN_TEXT.finditer(text):
            raw = m.group(0)
            val = m.group(1).replace(",", ".")
            try:
                n = float(val)
            except ValueError:
                continue
            if _KW_HINT.search(raw) and 5 <= n <= 600:
                n = n / 0.7355
            if 10 <= n <= 800:
                found.append(n)
    return found


def _extract_hp_from_nested(car_data: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Эвристика: несколько значений мощности в extra/spec — меньшее как ДВС, большее как ЭД или системная."""
    texts = _iter_nested_strings(
        {
            "extra": car_data.get("extra"),
            "spec": (car_data.get("extra") or {}).get("spec") if isinstance(car_data.get("extra"), dict) else None,
            "description": car_data.get("description"),
            "gradeName": car_data.get("gradeName"),
            "generation": car_data.get("generation"),
        }
    )
    hp_list = sorted(set(_scan_texts_for_hp(texts)))
    if len(hp_list) >= 2:
        return hp_list[0], hp_list[-1]
    if len(hp_list) == 1:
        return hp_list[0], None
    return None, None


_ED_THIRTY_MIN_HP_FACTOR = 0.45


def _ed_thirty_min_hp(hp_peak: float) -> float:
    return max(0.0, float(hp_peak)) * _ED_THIRTY_MIN_HP_FACTOR


_SERIES_HYBRID_MARKERS = (
    "e-power",
    "e power",
    "epower",
    "이-power",
    "이파워",
    "serial hybrid",
    "series hybrid",
    "последовательн",
    "range extender",
    "range-extender",
)
_PHEV_MARKERS = (
    "phev",
    "plug-in",
    "plug in",
    "plug-in hybrid",
    "플러그",
    "플러그인",
)
HYBRID_CATALOG_FUEL_LABELS = frozenset(
    {
        "Гибрид (Бензин)",
        "Гибрид (Дизель)",
        "Подключаемый гибрид (PHEV)",
    }
)


def _canon_fuel_label(raw: Any) -> str:
    s = _norm_ws(raw)
    if not s:
        return ""
    try:
        from fastapi_app.facet_normalize import canon_catalog_fuel_ru

        return _norm_ws(canon_catalog_fuel_ru(s))
    except ImportError:
        return s


def is_hybrid_listing(car_data: Dict[str, Any]) -> bool:
    """True если авто попадает в фильтры «Гибрид (Бензин)» / «Гибрид (Дизель)» / PHEV."""
    if not isinstance(car_data, dict):
        return False
    for key in ("engine_type", "engine_type_ru", "engine_type_original", "fuel", "engineType"):
        canon = _canon_fuel_label(car_data.get(key))
        if canon in HYBRID_CATALOG_FUEL_LABELS:
            return True
    try:
        from market_pricing_shared import classify_fuel

        return classify_fuel(car_data) == "hybrid"
    except ImportError:
        return False


def _hybrid_is_diesel(car_data: Dict[str, Any]) -> bool:
    for key in ("engine_type", "engine_type_ru", "engine_type_original", "fuel"):
        s = _norm_ws(car_data.get(key)).lower()
        if not s:
            continue
        if "дизель" in s or "diesel" in s or "디젤" in s:
            return True
    return _canon_fuel_label(car_data.get("engine_type")) == "Гибрид (Дизель)"


def _estimate_parallel_ed_hp(ice: float, cc: Optional[int], *, diesel: bool) -> float:
    """Оценка пика ЭД для parallel HEV, если нет заводских данных (типичные корейские установки)."""
    hp = max(10.0, float(ice))
    if cc is not None and cc > 0:
        if cc <= 1650:
            ratio = 0.36 if hp >= 150 else 0.414
            return round(hp * ratio, 1)
        if cc <= 2500:
            ratio = 0.30 if diesel else 0.335
            return round(max(40.0, hp * ratio), 1)
        if cc <= 3500:
            return round(hp * 0.28, 1)
    return round(hp * (0.30 if diesel else 0.35), 1)


_PARALLEL_HYBRID_MARKERS = (
    "hev",
    "mhev",
    "hybrid",
    "하이브리드",
    "parallel",
    "параллельн",
)

# Платформенный fallback: объём + мощность ДВС → типичный пик ЭД (Kappa 1.6 / Smartstream 1.6 HEV и т.д.)
_PLATFORM_ED_BY_CC_ICE: Tuple[Tuple[int, int, int, float], ...] = (
    (1580, 1600, 105, 43.5),
    (1590, 1610, 180, 65.0),
    (1990, 2010, 152, 51.0),
    (2340, 2370, 159, 51.0),
)


def infer_hybrid_layout(car_data: Dict[str, Any]) -> str:
    """
    parallel — HEV/PHEV: сумма пиков ДВС + ЭД в витрине и таможне.
    series — e-POWER: только ЭД (ДВС — генератор).
    """
    if not isinstance(car_data, dict):
        return "parallel"
    explicit = str(car_data.get("hybrid_layout") or car_data.get("hybrid_type") or "").strip().lower()
    if explicit in ("series", "serial", "series_hybrid", "последовательный"):
        return "series"
    if explicit in ("parallel", "parallel_hybrid", "параллельный"):
        return "parallel"

    blob = " ".join(
        _norm_ws(car_data.get(k))
        for k in (
            "engine_type",
            "engine_type_ru",
            "model",
            "modelName",
            "generation",
            "gradeName",
            "modelGroupName",
            "configuration",
            "description",
        )
    ).lower()

    if any(m in blob for m in _SERIES_HYBRID_MARKERS):
        return "series"
    if any(m in blob for m in _PHEV_MARKERS):
        return "parallel"
    if any(m in blob for m in _PARALLEL_HYBRID_MARKERS):
        return "parallel"
    return "parallel"


def catalog_rated_power_hp(car_data: Dict[str, Any]) -> Optional[int]:
    """Полная мощность для витрины/фасетов (л.с.)."""
    if not isinstance(car_data, dict):
        return None
    try:
        from market_pricing_shared import classify_fuel
    except ImportError:
        classify_fuel = None  # type: ignore

    if classify_fuel:
        fuel = classify_fuel(car_data)
        if fuel == "electric":
            peak = _electric_hp_from_car(car_data) or _parse_hp_value(car_data.get("power"))
            return int(round(peak)) if peak is not None else None
        if fuel == "hybrid" or is_hybrid_listing(car_data):
            comp = resolve_hybrid_components(car_data)
            if not comp:
                return None
            layout = infer_hybrid_layout(car_data)
            ice = comp["ice_hp"]
            ed = comp.get("electric_hp")
            if layout == "series":
                return int(round(ed)) if ed else None
            if ed:
                return int(round(ice + ed))
            return int(round(ice))

    hp = _parse_hp_value(car_data.get("power_hp") or car_data.get("power"))
    return int(round(hp)) if hp is not None else None


@lru_cache(maxsize=1)
def _load_specs() -> List[Dict[str, Any]]:
    if not _specs_file().exists():
        return []
    try:
        with open(_specs_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        specs = data.get("specs") if isinstance(data, dict) else data
        return [x for x in specs if isinstance(x, dict)] if isinstance(specs, list) else []
    except Exception:
        return []


def _model_blob(car_data: Dict[str, Any]) -> str:
    return " ".join(
        _norm_ws(car_data.get(k))
        for k in ("model", "modelName", "generation", "gradeName", "modelGroupName", "configuration", "mark")
    ).lower()


def _platform_ed_fallback(car_data: Dict[str, Any], ice: float) -> Optional[float]:
    cc = _car_cc(car_data)
    if cc is None or ice <= 0:
        return None
    ice_i = int(round(ice))
    for cc_lo, cc_hi, ice_nom, ed in _PLATFORM_ED_BY_CC_ICE:
        if cc_lo <= cc <= cc_hi and abs(ice_i - ice_nom) <= 3:
            return float(ed)
    return None


def _estimate_ice_hp_from_cc(cc: Optional[int], *, diesel: bool) -> Optional[float]:
    """Типичная мощность ДВС по объёму, если Encar не отдал power."""
    if cc is None or cc <= 0:
        return None
    if cc <= 1200:
        return 82.0
    if cc <= 1600:
        return 136.0 if diesel else 105.0
    if cc <= 2000:
        return 152.0
    if cc <= 2500:
        return 180.0 if diesel else 159.0
    if cc <= 3500:
        return 278.0
    return round(cc * 0.07, 1)


def _match_spec_rule(car_data: Dict[str, Any], rule: Dict[str, Any]) -> Optional[Dict[str, float]]:
    makes = rule.get("make") or []
    if makes:
        mark = _norm_ws(car_data.get("mark") or car_data.get("manufacturerName"))
        if not any(m.lower() in mark.lower() or mark.lower() in str(m).lower() for m in makes):
            return None

    blob = _model_blob(car_data)
    subs_any = rule.get("model_substrings") or []
    if subs_any and not any(str(s).lower() in blob for s in subs_any):
        return None
    subs_all = rule.get("model_substrings_all") or []
    if subs_all and not all(str(s).lower() in blob for s in subs_all):
        return None
    if not subs_any and subs_all and not all(str(s).lower() in blob for s in subs_all):
        return None

    cc = _car_cc(car_data)
    if cc is not None:
        cmin = rule.get("cc_min")
        cmax = rule.get("cc_max")
        if cmin is not None and cc < int(cmin):
            return None
        if cmax is not None and cc > int(cmax):
            return None

    ice = _ice_hp_from_car(car_data)
    if ice is not None:
        if rule.get("ice_hp") is not None and int(round(ice)) != int(rule["ice_hp"]):
            return None
        ih_min = rule.get("ice_hp_min")
        ih_max = rule.get("ice_hp_max")
        if ih_min is not None and ice < float(ih_min) - 2:
            return None
        if ih_max is not None and ice > float(ih_max) + 2:
            return None

    out: Dict[str, float] = {}
    if rule.get("ice_hp") is not None:
        out["ice_hp"] = float(rule["ice_hp"])
    elif ice is not None:
        out["ice_hp"] = float(ice)
    elif rule.get("ice_hp_min") is not None and rule.get("ice_hp_max") is not None:
        out["ice_hp"] = round((float(rule["ice_hp_min"]) + float(rule["ice_hp_max"])) / 2, 1)
    elif rule.get("system_hp") is not None and rule.get("electric_hp") is not None:
        out["ice_hp"] = float(rule["system_hp"]) - float(rule["electric_hp"])
    if rule.get("electric_hp") is not None:
        out["electric_hp"] = float(rule["electric_hp"])
    if rule.get("system_hp") is not None:
        out["system_hp"] = float(rule["system_hp"])
    return out if out else None


def lookup_hybrid_factory_spec(car_data: Dict[str, Any]) -> Optional[Dict[str, float]]:
    best: Optional[Dict[str, float]] = None
    best_score = -1
    ice_obs = _ice_hp_from_car(car_data)
    for rule in _load_specs():
        matched = _match_spec_rule(car_data, rule)
        if not matched:
            continue
        score = 0
        if rule.get("ice_hp") is not None and ice_obs is not None:
            if int(round(ice_obs)) == int(rule["ice_hp"]):
                score += 10
        if rule.get("model_substrings"):
            score += len(rule.get("model_substrings") or [])
        if best is None or score > best_score:
            best = matched
            best_score = score
    return best


def resolve_hybrid_components(car_data: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Возвращает ice_hp, electric_hp, system_hp (для витрины) или None если не гибрид."""
    if not is_hybrid_listing(car_data):
        return None

    ice = _ice_hp_from_car(car_data)
    ed = _electric_hp_from_car(car_data)
    system: Optional[float] = _parse_hp_value(car_data.get("power_hp_system"))
    estimated_ed = False

    factory = lookup_hybrid_factory_spec(car_data)
    if factory:
        if ice is None and factory.get("ice_hp"):
            ice = factory["ice_hp"]
        if ed is None and factory.get("electric_hp"):
            ed = factory["electric_hp"]
        if system is None and factory.get("system_hp"):
            system = factory["system_hp"]
        if ice is None and system is not None and ed is not None:
            ice = float(system) - float(ed)

    if ice is None or ed is None:
        n_ice, n_ed = _extract_hp_from_nested(car_data)
        if ice is None:
            ice = n_ice
        if ed is None and n_ed is not None and n_ice is not None and n_ed > n_ice:
            ed = n_ed

    if ed is None and ice is not None:
        plat_ed = _platform_ed_fallback(car_data, float(ice))
        if plat_ed is not None:
            ed = plat_ed

    layout = infer_hybrid_layout(car_data)
    if ed is None and ice is not None and layout != "series":
        ed = _estimate_parallel_ed_hp(float(ice), _car_cc(car_data), diesel=_hybrid_is_diesel(car_data))
        estimated_ed = True
    elif ed is None and ice is not None and layout == "series":
        # e-POWER: в объявлении часто только ДВС-генератор — оцениваем пик ЭД выше ДВС
        ed = max(float(ice) * 1.5, _estimate_parallel_ed_hp(float(ice), _car_cc(car_data), diesel=False))
        estimated_ed = True

    if system is None and ice is not None and ed is not None:
        system = round(ice + ed) if layout != "series" else round(ed)
    if ice is None:
        cc = _car_cc(car_data)
        ice = _estimate_ice_hp_from_cc(cc, diesel=_hybrid_is_diesel(car_data))
        if ice is not None and ed is None and layout != "series":
            ed = _estimate_parallel_ed_hp(float(ice), cc, diesel=_hybrid_is_diesel(car_data))
            estimated_ed = True
    if ice is None:
        return None
    result: Dict[str, float] = {"ice_hp": float(ice)}
    if ed is not None and ed > 0:
        result["electric_hp"] = float(ed)
    if system is not None and system > 0:
        result["system_hp"] = float(system)
    if estimated_ed:
        result["estimated"] = 1.0
    return result


def enrich_hybrid_power_fields(car_data: Dict[str, Any]) -> bool:
    """
    Записывает power_ice_hp, power_electric_hp, hybrid_layout и power/power_hp
    (полная мощность для витрины). Возвращает True, если поля обновлены.
    """
    if not isinstance(car_data, dict):
        return False
    comp = resolve_hybrid_components(car_data)
    if not comp:
        return False

    ice = comp["ice_hp"]
    ed = comp.get("electric_hp")
    layout = infer_hybrid_layout(car_data)
    car_data["hybrid_layout"] = layout

    if ed is not None:
        car_data["power_ice_hp"] = int(round(ice))
        car_data["power_electric_hp"] = int(round(ed))
    if comp.get("system_hp") is not None:
        car_data["power_hp_system"] = int(round(comp["system_hp"]))

    if layout == "series":
        if ed is None:
            return False
        display = int(round(ed))
    elif ed is not None:
        display = int(ice + ed + 0.5)
    else:
        return False

    prev = _parse_hp_value(car_data.get("power"))
    car_data["power"] = str(display)
    car_data["power_hp"] = display
    if comp.get("estimated"):
        car_data.setdefault("power_source", "hybrid_power_estimate")
        car_data["power_estimated"] = True
    elif prev is not None and int(round(prev)) == int(round(ice)) and ed is not None:
        car_data.setdefault("power_source", "hybrid_power_specs")
        car_data["power_estimated"] = True
    return True


def catalog_display_power_hp(car_data: Dict[str, Any]) -> Optional[int]:
    """Мощность для карточки/фасетов."""
    enrich_hybrid_power_fields(car_data)
    return catalog_rated_power_hp(car_data)
