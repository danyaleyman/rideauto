# -*- coding: utf-8 -*-
"""
Мощность (л.с.) для рынка США (Autotrader, source=autotrader|usa).

Порядок подбора (только для карточек США — Корея/Китай не затрагиваются):
1) NHTSA vPIC по VIN — заводское значение (кеш data/vin_power_cache.json);
2) data/us_engine_map.json — кураторский каталог make/model/cc/fuel/year.

Зачем: Autotrader VDP отдаёт только engineDescription без HP, поэтому ~474 карточки
уходили в price_on_request (нужны и displacement_cc, и power_hp для полной таможни РФ).
vPIC закрывает ~28%, остаток добирает каталог по номинальному объёму (2000/3500/...).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engine_hp_resolver import normalize_cc_100, resolve_hp_from_entries

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
US_ENGINE_MAP_PATH = DATA_DIR / "us_engine_map.json"
VIN_CACHE_PATH = DATA_DIR / "vin_power_cache.json"

# Рынки, для которых работает этот модуль. Всё прочее (encar, che168, …) игнорируем.
US_SOURCES = frozenset({"autotrader", "usa"})

VPIC_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")  # VIN без I, O, Q
_VIN_CACHE_TTL_SEC = 400 * 24 * 3600  # ~13 месяцев
# Если vPIC не отдал hp (старая машина / неизвестный VIN) — перезапрашиваем через 30 дней,
# чтобы библиотека могла подрасти, а не «залипала» на пустом ответе навсегда.
_VIN_CACHE_NOHP_TTL_SEC = 30 * 24 * 3600


def _vin_lookup_enabled() -> bool:
    raw = str(os.environ.get("USA_VIN_POWER", "1") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _vin_timeout() -> float:
    try:
        return float(os.environ.get("USA_VIN_POWER_TIMEOUT", "6") or 6)
    except ValueError:
        return 6.0


def ingest_vin_lookup_enabled() -> bool:
    """
    Ходить ли в vPIC прямо на ingest (парсинг). По умолчанию нет: слой каталога офлайн
    и не тормозит скрапер, а vPIC всё равно отработает в postgres_catalog_sync.
    Включение: USA_VIN_POWER_AT_INGEST=1.
    """
    raw = str(os.environ.get("USA_VIN_POWER_AT_INGEST", "0") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def is_usa_source(car_data: Dict[str, Any]) -> bool:
    """True только для карточек Autotrader/США; иначе чужие пайплайны не трогаем."""
    if not isinstance(car_data, dict):
        return False
    src = str(car_data.get("source") or "").strip().lower()
    if src:
        return src in US_SOURCES
    return str(car_data.get("market") or car_data.get("region") or "").strip().lower() == "usa"


def _to_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        f = float(str(v).replace(",", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return None
    return int(round(f)) if f > 0 else None


def usa_engine_cc(car_data: Dict[str, Any]) -> Optional[int]:
    """
    Объём (см³) для карточки США. Явные cc-поля важнее строки-ярлыка:
    `displacement` у Autotrader бывает «2.0L», и _car_cc() вытащил бы из неё «20».
    """
    if not isinstance(car_data, dict):
        return None
    try:
        from market_pricing_shared import parse_engine_cc
    except ImportError:  # офлайн-утилиты без backend в sys.path
        parse_engine_cc = None  # type: ignore[assignment]

    for key in ("displacement_cc", "engine_volume", "engine_volume_cc"):
        v = car_data.get(key)
        if v in (None, ""):
            continue
        cc = _to_int(v)
        if cc is None and parse_engine_cc is not None:
            cc = parse_engine_cc(v)
        if cc is not None and 500 <= int(cc) <= 9000:
            return int(cc)

    disp = car_data.get("displacement")
    if disp not in (None, ""):
        cc = _to_int(disp)
        if cc is None and parse_engine_cc is not None:
            cc = parse_engine_cc(disp)  # «2.0L» / 2.0 → 2000
        if cc is not None and 500 <= int(cc) <= 9000:
            return int(cc)
    return None


def _has_power(car_data: Dict[str, Any]) -> bool:
    for key in ("power", "power_hp", "power_kw"):
        v = car_data.get(key)
        if v is None or str(v).strip() == "":
            continue
        digits = re.sub(r"[^\d]", "", str(v))
        if digits and int(digits) > 0:
            return True
    return False


def _set_power(car_data: Dict[str, Any], hp: int, source_label: str) -> None:
    car_data["power_hp"] = int(hp)
    car_data["power"] = str(int(hp))
    car_data["power_source"] = source_label
    car_data["power_estimated"] = True


# Кеш каталога: (mtime_ns, size) → записи (файл правят редко, карточек много).
_us_map_cache_key: Optional[tuple] = None
_us_map_cache: List[Dict[str, Any]] = []


def _load_us_engine_map() -> List[Dict[str, Any]]:
    global _us_map_cache, _us_map_cache_key
    if not US_ENGINE_MAP_PATH.exists():
        return []
    key: Optional[tuple] = None
    try:
        st = US_ENGINE_MAP_PATH.stat()
        key = (int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        key = None
    if key is not None and key == _us_map_cache_key:
        return _us_map_cache
    try:
        with open(US_ENGINE_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # битый JSON не должен ломать прайсинг
        logger.warning("us_engine_map.json load failed: %s", e)
        return _us_map_cache
    engines = data.get("engines") if isinstance(data, dict) else data
    if not isinstance(engines, list):
        return _us_map_cache
    _us_map_cache = [x for x in engines if isinstance(x, dict)]
    _us_map_cache_key = key
    return _us_map_cache


def invalidate_us_engine_map_cache() -> None:
    """Сбросить кеш каталога (тесты/скрипты после правки us_engine_map.json)."""
    global _us_map_cache_key
    _us_map_cache_key = None


# --- кеш vPIC по VIN (файл, чтобы не дёргать NHTSA на каждом прогоне синка) ---

_vin_cache: Optional[Dict[str, Dict[str, Any]]] = None
_vin_cache_dirty = False


def _load_vin_cache() -> Dict[str, Dict[str, Any]]:
    global _vin_cache
    if _vin_cache is None:
        loaded: Dict[str, Dict[str, Any]] = {}
        try:
            if VIN_CACHE_PATH.is_file():
                raw = json.loads(VIN_CACHE_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if isinstance(v, dict):
                            loaded[str(k).strip().upper()] = v
        except Exception as e:
            logger.warning("vin_power_cache load failed: %s", e)
        _vin_cache = loaded
    return _vin_cache


def _vin_cache_flush(force: bool = False) -> None:
    """Записать кеш на диск (best-effort: read-only каталог не должен ломать прайсинг)."""
    global _vin_cache_dirty
    if not _vin_cache_dirty and not force:
        return
    try:
        payload = json.dumps(_load_vin_cache(), ensure_ascii=False, indent=1, sort_keys=True)
        tmp = VIN_CACHE_PATH.with_name(VIN_CACHE_PATH.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(VIN_CACHE_PATH)
        _vin_cache_dirty = False
    except OSError as e:
        logger.debug("vin_power_cache save failed: %s", e)


def _vpic_query(vin: str) -> Dict[str, Any]:
    url = VPIC_URL.format(vin=urllib.parse.quote(vin))
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "RideAuto/1.0 (USA power resolver)"},
    )
    with urllib.request.urlopen(req, timeout=_vin_timeout()) as resp:
        payload = json.loads(resp.read().decode("utf-8", "replace"))
    results = payload.get("Results") if isinstance(payload, dict) else None
    row = results[0] if isinstance(results, list) and results else {}
    return row if isinstance(row, dict) else {}


def _parse_vpic_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Нормализовать строку vPIC: hp (макс. из EngineHP/EngineHP_to), cc, признак BEV."""
    hp_from, hp_to = _to_int(row.get("EngineHP")), _to_int(row.get("EngineHP_to"))
    candidates = [x for x in (hp_from, hp_to) if x]
    # Для акциза берём максимальную мощность двигателя.
    hp = max(candidates) if candidates else None
    if hp is not None and not (20 <= hp <= 2500):
        hp = None

    cc = _to_int(row.get("DisplacementCC"))
    if cc is None:
        try:
            liters = float(str(row.get("DisplacementL") or "").replace(",", ".").strip())
        except (TypeError, ValueError):
            liters = 0.0
        if 0.5 <= liters <= 9.0:
            cc = int(round(liters * 1000))
    if cc is not None and not (500 <= cc <= 9000):
        cc = None

    level = str(row.get("ElectrificationLevel") or "").upper()
    fuel = str(row.get("FuelTypePrimary") or "").upper()
    electric = "BEV" in level or ("ELECTRIC" in fuel and "HYBRID" not in level)

    return {
        "hp": hp,
        "cc": cc,
        "electric": bool(electric),
        "make": str(row.get("Make") or "").strip() or None,
        "model": str(row.get("Model") or "").strip() or None,
        "year": _to_int(row.get("ModelYear")),
        "ts": int(time.time()),
    }


def lookup_vin_power(vin: str, *, use_cache: bool = True) -> Optional[Dict[str, Any]]:
    """
    Данные двигателя по VIN из NHTSA vPIC (с файловым кешем).
    Возвращает {'hp','cc','electric','make','model','year','ts'} или None.
    """
    v = str(vin or "").strip().upper()
    if not _VIN_RE.match(v):
        return None

    cache = _load_vin_cache()
    hit = cache.get(v)
    if use_cache and isinstance(hit, dict):
        age = int(time.time()) - int(hit.get("ts") or 0)
        ttl = _VIN_CACHE_TTL_SEC if hit.get("hp") else _VIN_CACHE_NOHP_TTL_SEC
        if 0 <= age < ttl:
            return hit if hit.get("hp") else None

    if not _vin_lookup_enabled():
        return None
    try:
        info = _parse_vpic_row(_vpic_query(v))
    except Exception as e:  # сеть/таймаут/битый ответ — не мешаем прайсингу
        logger.info("vPIC lookup failed for %s: %s", v[-6:], e)
        return None

    global _vin_cache_dirty
    cache[v] = info
    _vin_cache_dirty = True
    _vin_cache_flush()
    return info if info.get("hp") else None


def fill_usa_power(car_data: Dict[str, Any], *, allow_vin: bool = True) -> bool:
    """
    Заполнить power/power_hp для карточки США (vPIC по VIN → us_engine_map).
    True — если мощность найдена и записана. Корея/Китай не обрабатываются.
    """
    if not is_usa_source(car_data) or _has_power(car_data):
        return False

    if allow_vin:
        vin = str(car_data.get("vin") or "").strip()
        info = lookup_vin_power(vin) if vin else None
        if info:
            cc = _to_int(info.get("cc"))
            # vPIC знает точный объём — добираем, если у карточки пусто.
            if cc and usa_engine_cc(car_data) is None:
                car_data["displacement_cc"] = int(cc)
                car_data.setdefault("engine_volume", int(cc))
            if info.get("electric") and not str(car_data.get("engine_type") or "").strip():
                car_data["engine_type"] = "Electric"
            hp = _to_int(info.get("hp"))
            if hp:
                _set_power(car_data, hp, "vin_vpic")
                return True

    entries = _load_us_engine_map()
    if entries:
        hp = resolve_hp_from_entries(
            car_data,
            entries,
            source_label="us_engine_map",
            normalize_cc=True,
            cc_override=usa_engine_cc(car_data),
        )
        if hp:
            _set_power(car_data, int(hp), "us_engine_map")
            return True
    return False


def enrich_usa_power_at_ingest(car_data: Dict[str, Any]) -> bool:
    """
    Присвоить мощность уже на ingest (парсинг Autotrader), из нашей HP-библиотеки.

    Слой `us_engine_map.json` — офлайн и мгновенно, поэтому карточка попадает в БД
    сразу с power_hp/displacement_cc. vPIC по VIN подключается только при
    USA_VIN_POWER_AT_INGEST=1 (иначе сеть не тормозит скрапер — vPIC добьёт
    postgres_catalog_sync). Корея/Китай не затрагиваются (см. is_usa_source).
    """
    return fill_usa_power(car_data, allow_vin=ingest_vin_lookup_enabled())


def _fuel_key(engine_type: Any) -> str:
    """Топливо в терминах us_engine_map.json (как engine_hp_resolver._fuel_bucket)."""
    if engine_type is None or str(engine_type).strip() == "":
        return "gas"
    s, ko = str(engine_type).lower(), str(engine_type)
    if "electric" in s or "электро" in s or "전기" in ko or s.strip() in ("ev", "bev"):
        return "electric"
    if "hybrid" in s or "гибрид" in s or "hev" in s or "phev" in s or "하이브리드" in ko:
        return "hybrid"
    if "diesel" in s or "дизел" in s or "디젤" in ko:
        return "diesel"
    if "lpg" in s or "가스" in ko:
        return "lpg"
    return "gas"


def _median_int(values: List[int]) -> Optional[int]:
    vals = sorted(int(v) for v in values if v)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return int(round((vals[mid - 1] + vals[mid]) / 2))


def suggest_library_entries(
    samples: List[Dict[str, Any]],
    *,
    min_count: int = 1,
    default_priority: int = 5,
) -> List[Dict[str, Any]]:
    """
    Кандидаты в `data/us_engine_map.json` из наблюдений vPIC (реальные VIN).

    sample: {"make", "model", "cc", "fuel", "year", "hp"} — как отдаёт vPIC/наш кеш.
    Группировка: make + модель (строка целиком, lower) + номинальный cc (кратно 100) + топливо.
    hp — медиана по выборке, year_min/year_max — границы модельных годов.

    Библиотека растёт вручную: скрипт backend/scripts/usa_engine_map_suggest.py
    печатает такие записи, их остаётся добавить в JSON (или смёржить под ревью).
    """
    buckets: Dict[Tuple[str, str, int, str], Dict[str, Any]] = {}
    for s in samples or []:
        if not isinstance(s, dict):
            continue
        make = str(s.get("make") or "").strip()
        model = str(s.get("model") or "").strip().lower()
        hp = _to_int(s.get("hp"))
        cc = _to_int(s.get("cc"))
        if not make or not model or not hp or not cc or not (20 <= hp <= 2500):
            continue
        cc_norm = normalize_cc_100(int(cc))
        if cc_norm is None or not (500 <= int(cc_norm) <= 9000):
            continue
        fuel = _fuel_key(s.get("fuel"))
        key = (make.lower(), model, int(cc_norm), fuel)
        b = buckets.setdefault(
            key,
            {
                "make": make,
                "model": model,
                "cc": int(cc_norm),
                "fuel": fuel,
                "hps": [],
                "years": [],
                "samples": 0,
            },
        )
        b["hps"].append(hp)
        b["samples"] += 1
        y = _to_int(s.get("year"))
        if y and 1980 <= y <= 2035:
            b["years"].append(y)

    out: List[Dict[str, Any]] = []
    for b in buckets.values():
        if int(b["samples"]) < max(1, int(min_count)):
            continue
        years: List[int] = b["years"]
        entry: Dict[str, Any] = {
            "make": b["make"],
            "model_substrings": [b["model"]],
            "cc": b["cc"],
            "fuel": b["fuel"],
            "hp": _median_int(b["hps"]),
            "priority": int(default_priority),
            "samples": int(b["samples"]),
        }
        if years:
            entry["year_min"] = min(years)
            entry["year_max"] = max(years)
        out.append(entry)
    out.sort(key=lambda e: (-int(e.get("samples") or 0), e["make"], e["model_substrings"][0], e["cc"]))
    return out


def flush_vin_cache() -> None:
    """Принудительно сбросить кеш vPIC на диск (скрипты/батч-бэкфилл)."""
    _vin_cache_flush(force=True)


