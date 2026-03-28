# -*- coding: utf-8 -*-
"""
Оценка мощности (л.с.) по каталогу двигателей (engine_map.json).

Encar часто не отдаёт power — конкуренты обогащают данные: марка + модель + объём + топливо + турбо → HP.
Схема: нормализация марки (encar_mapping.json) + матч по engine_map + метаданные power_source / power_estimated.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "frontend" / "data"
ENGINE_MAP_PATH = DATA_DIR / "engine_map.json"
ENC_MAPPING_PATH = DATA_DIR / "encar_mapping.json"


def _norm_ws(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip())


def _norm_make_key(s: str) -> str:
    """Ключ для сравнения марок: буквы/цифры в lower."""
    return re.sub(r"[^a-z0-9가-힣]", "", (s or "").lower())


def _norm_make_en(s: str) -> str:
    """Латиница для сравнения с полем make в engine_map."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


@lru_cache(maxsize=1)
def _load_mark_ko_to_en() -> Dict[str, str]:
    if not ENC_MAPPING_PATH.exists():
        return {}
    try:
        with open(ENC_MAPPING_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("mark") or {}
        if not isinstance(raw, dict):
            return {}
        return {str(k).strip(): str(v).strip() for k, v in raw.items() if k and v}
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _load_engine_map() -> List[Dict[str, Any]]:
    if not ENGINE_MAP_PATH.exists():
        return []
    try:
        with open(ENGINE_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict) and isinstance(data.get("engines"), list):
            return [x for x in data["engines"] if isinstance(x, dict)]
    except Exception:
        pass
    return []


def _car_year(car_data: Dict[str, Any]) -> Optional[int]:
    y = car_data.get("year") or car_data.get("yearMonth") or ""
    if not y:
        return None
    digits = re.sub(r"\D", "", str(y)[:8])
    if len(digits) < 4:
        return None
    try:
        yi = int(digits[:4])
        return yi if 1980 <= yi <= 2035 else None
    except ValueError:
        return None


def _car_cc(car_data: Dict[str, Any]) -> Optional[int]:
    disp = car_data.get("displacement") or car_data.get("engine_volume")
    if disp is None or disp == "":
        return None
    try:
        n = int(re.sub(r"\D", "", str(disp)))
        if 500 <= n <= 8000:
            return n
    except ValueError:
        pass
    return None


def _fuel_bucket(engine_type: Any) -> Optional[str]:
    if engine_type is None or str(engine_type).strip() == "":
        return None
    s = str(engine_type).lower()
    ko = str(engine_type)
    if "전기" in ko or "electric" in s:
        return "electric"
    if "하이브리드" in ko or "hybrid" in s or "hev" in s or "phev" in s:
        return "hybrid"
    if "디젤" in ko or "diesel" in s:
        return "diesel"
    if "lpg" in s or "가스" in ko:
        return "lpg"
    if "수소" in ko or "hydrogen" in s:
        return "hydrogen"
    return "gas"


def extract_motor_code(car_data: Dict[str, Any]) -> str:
    """
    Код/тип двигателя из отчёта инспекции Encar (master.detail.motorType).
    Примеры: B48A20E, D4HB, 256930.
    """
    if not isinstance(car_data, dict):
        return ""
    extra = car_data.get("extra")
    if not isinstance(extra, dict):
        extra = {}
    insp = extra.get("inspection")
    if not isinstance(insp, dict):
        insp = {}
    master = insp.get("master")
    if not isinstance(master, dict):
        master = {}
    detail = master.get("detail")
    if not isinstance(detail, dict):
        detail = {}
    mt = detail.get("motorType") or detail.get("motor_type") or detail.get("engineCode")
    if mt:
        return re.sub(r"\s+", "", str(mt).strip().upper())
    return ""


def _combined_text(car_data: Dict[str, Any]) -> str:
    parts = []
    for k in (
        "gradeName",
        "generation",
        "configuration",
        "modelName",
        "model",
        "modelGroupName",
        "mark",
        "manufacturerName",
    ):
        v = car_data.get(k)
        if v:
            parts.append(str(v))
    return " ".join(parts).lower()


def detect_turbo(car_data: Dict[str, Any]) -> bool:
    """Турбина по тексту комплектации; дизель на Encar почти всегда турбодизель (CRDi/TDI)."""
    if _fuel_bucket(car_data.get("engine_type")) == "diesel":
        return True
    blob = _combined_text(car_data)
    if not blob:
        return False
    if "터보" in blob or "turbo" in blob or "twinturbo" in blob or "twin turbo" in blob:
        return True
    if "t-gdi" in blob or "tgdi" in blob or "gdi t" in blob:
        return True
    if re.search(r"\b\d\.\d\s*t\b", blob, re.IGNORECASE):
        return True
    if "crdi" in blob or "tdi" in blob:
        return True
    if "ecoboost" in blob:
        return True
    if "jcw" in blob:
        return True
    if "cooper s" in blob or "쿠퍼 s" in blob or "쿠퍼s" in blob.replace(" ", ""):
        return True
    return False


def _canonical_make_en(car_data: Dict[str, Any]) -> str:
    raw = (
        car_data.get("manufacturerName")
        or car_data.get("mark")
        or car_data.get("manufacturer")
        or ""
    )
    raw = _norm_ws(raw)
    if not raw:
        return ""
    ko_map = _load_mark_ko_to_en()
    if raw in ko_map:
        return _norm_make_en(ko_map[raw])
    # Уже латиница / англ. имя с Encar
    for ko, en in ko_map.items():
        if raw.lower() == ko.lower():
            return _norm_make_en(en)
    return _norm_make_en(raw)


def _model_blob(car_data: Dict[str, Any]) -> str:
    parts = [
        car_data.get("modelName"),
        car_data.get("model"),
        car_data.get("modelGroupName"),
        car_data.get("generation"),
        car_data.get("configuration"),
        car_data.get("gradeName"),
    ]
    return " ".join(_norm_ws(p) for p in parts if p).lower()


def _entry_make_keys(entry: Dict[str, Any]) -> List[str]:
    keys = []
    for k in ("make", "brand"):
        v = entry.get(k)
        if v:
            keys.append(_norm_make_en(str(v)))
    mk = entry.get("make_ko")
    if mk:
        ko_map = _load_mark_ko_to_en()
        if str(mk).strip() in ko_map:
            keys.append(_norm_make_en(ko_map[str(mk).strip()]))
        keys.append(_norm_make_key(str(mk)))
    return [x for x in keys if x]


def _make_matches(entry: Dict[str, Any], car_make_en: str, car_make_raw_key: str) -> bool:
    mk_raw_entry = _norm_make_key(entry.get("make_ko") or "")
    if mk_raw_entry and car_make_raw_key and mk_raw_entry == car_make_raw_key:
        return True
    if not car_make_en:
        return False
    ek = _entry_make_keys(entry)
    if not ek:
        return False
    for k in ek:
        if k == car_make_en or car_make_en.startswith(k) or k.startswith(car_make_en):
            return True
    return False


def _motor_codes_match(entry: Dict[str, Any], car_motor: str) -> bool:
    """Совпадение по motor_codes / engine_codes (точное или префикс ≥4 символа)."""
    codes = entry.get("motor_codes") or entry.get("engine_codes") or []
    if not codes:
        return True
    if not car_motor:
        return False
    cm = car_motor.upper().strip()
    for c in codes:
        cu = str(c).upper().strip()
        if not cu:
            continue
        if cm == cu:
            return True
        if len(cu) >= 4 and (cm.startswith(cu) or cu.startswith(cm)):
            return True
    return False


def _model_matches(entry: Dict[str, Any], model_blob: str) -> bool:
    subs = entry.get("model_substrings") or entry.get("models") or []
    if not subs:
        return bool(entry.get("match_all_models"))
    if not model_blob:
        return False
    for sub in subs:
        s = str(sub).strip().lower()
        if s and s in model_blob:
            return True
    return False


def _cc_matches(entry: Dict[str, Any], cc: Optional[int]) -> bool:
    if cc is None:
        # Нет объёма — только записи без жёсткого cc
        return entry.get("cc") is None and entry.get("cc_min") is None and entry.get("cc_max") is None
    ec = entry.get("cc")
    if ec is not None:
        try:
            if int(ec) != cc:
                return False
        except (TypeError, ValueError):
            return False
        return True
    lo = entry.get("cc_min")
    hi = entry.get("cc_max")
    if lo is not None or hi is not None:
        try:
            lo_i = int(lo) if lo is not None else 0
            hi_i = int(hi) if hi is not None else 99999
        except (TypeError, ValueError):
            return False
        return lo_i <= cc <= hi_i
    return True


def _turbo_matches(entry: Dict[str, Any], turbo: bool, car_fuel: Optional[str]) -> bool:
    et = entry.get("turbo")
    if et is None or et == "":
        return True
    ef = str(entry.get("fuel") or "").lower()
    # Дизель: в каталоге часто turbo:false, у машины detect_turbo=True — не отсекаем
    if ef == "diesel" and car_fuel == "diesel":
        return True
    return bool(et) == turbo


def _fuel_matches(entry: Dict[str, Any], fuel: Optional[str]) -> bool:
    ef = entry.get("fuel")
    if ef is None or ef == "":
        return True
    if fuel is None:
        return True
    return str(ef).lower() == str(fuel).lower()


def _year_matches(entry: Dict[str, Any], year: Optional[int]) -> bool:
    if year is None:
        return True
    ymn = entry.get("year_min") or entry.get("year_from")
    ymx = entry.get("year_max") or entry.get("year_to")
    try:
        if ymn is not None and year < int(ymn):
            return False
        if ymx is not None and year > int(ymx):
            return False
    except (TypeError, ValueError):
        return False
    return True


def _entry_specificity(entry: Dict[str, Any]) -> int:
    score = 0
    if entry.get("cc") is not None:
        score += 5
    if entry.get("cc_min") is not None or entry.get("cc_max") is not None:
        score += 3
    if entry.get("turbo") is not None and entry.get("turbo") != "":
        score += 2
    if entry.get("fuel"):
        score += 2
    if entry.get("year_min") or entry.get("year_max") or entry.get("year_from") or entry.get("year_to"):
        score += 2
    subs = entry.get("model_substrings") or entry.get("models") or []
    score += min(len(subs), 4)
    if entry.get("motor_codes") or entry.get("engine_codes"):
        score += 6
    return score


def resolve_engine_hp(
    car_data: Dict[str, Any],
    *,
    record_source: bool = False,
) -> Optional[int]:
    """
    Подобрать HP по engine_map.json. При record_source=True выставляет:
    power_source='engine_map', power_estimated=True (если нашли значение).
    """
    if not isinstance(car_data, dict):
        return None
    entries = _load_engine_map()
    if not entries:
        return None

    make_en = _canonical_make_en(car_data)
    make_raw_key = _norm_make_key(
        car_data.get("manufacturerName") or car_data.get("mark") or ""
    )
    model_blob = _model_blob(car_data)
    year = _car_year(car_data)
    cc = _car_cc(car_data)
    turbo = detect_turbo(car_data)
    fuel = _fuel_bucket(car_data.get("engine_type"))
    car_motor = extract_motor_code(car_data)

    if fuel == "electric":
        # Для электрокаров отдельные строки в карте (без cc) или пропуск
        pass

    best: Tuple[int, int, int, int] = (-1, -1, -1, 0)  # (score, specificity, priority, hp)
    best_hp: Optional[int] = None

    for entry in entries:
        if not _make_matches(entry, make_en, make_raw_key):
            continue
        has_motor_codes = bool(entry.get("motor_codes") or entry.get("engine_codes"))
        if has_motor_codes:
            if not _motor_codes_match(entry, car_motor):
                continue
            subs = entry.get("model_substrings") or entry.get("models") or []
            if subs and not _model_matches(entry, model_blob):
                continue
        else:
            if not _model_matches(entry, model_blob):
                continue
        if not _cc_matches(entry, cc):
            continue
        if not _turbo_matches(entry, turbo, fuel):
            continue
        if not _fuel_matches(entry, fuel):
            continue
        if not _year_matches(entry, year):
            continue

        try:
            hp = int(entry.get("hp") or entry.get("power") or 0)
        except (TypeError, ValueError):
            continue
        if not (20 <= hp <= 2000):
            continue

        priority = int(entry.get("priority") or 0)
        spec = _entry_specificity(entry)
        # Штраф, если у машины неизвестен cc, а в записи задан жёсткий cc — меньше уверенности
        loose_cc = cc is None and (
            entry.get("cc") is not None or entry.get("cc_min") is not None or entry.get("cc_max") is not None
        )
        match_score = 1000 + priority * 50 + spec * 10
        if loose_cc:
            match_score -= 80

        tie = (match_score, spec, priority, hp)
        if tie > best:
            best = tie
            best_hp = hp

    if best_hp is not None and record_source:
        car_data["power_source"] = "engine_map"
        car_data["power_estimated"] = True

    return best_hp
