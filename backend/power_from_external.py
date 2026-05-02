# -*- coding: utf-8 -*-
"""
Мощность (л.с.): 1) уже в данных авто, 2) hp_catalog «наблюдаемые» источники
   (PostgreSQL-синхронизация, CSV), 3) engine_map.json, 4) hp_catalog LLM-дозаполнение
   при достаточной уверенности, 5) power_lookup.json.

Если запись не найдена даже после LLM-индекса, добавляем pending для фона.

Индекс hp_catalog.db перестраивается при изменении mtime файла (без LRU на весь процесс).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
POWER_LOOKUP_PATH = DATA_DIR / "power_lookup.json"
HP_CATALOG_DB_PATH = DATA_DIR / "hp_catalog.db"
_NON_WORD_RE = re.compile(r"[^0-9a-zA-Z가-힣]+")

# Фактические строки каталога (не LLM-догадка).
HP_CATALOG_OBSERVED_SOURCES = frozenset({"postgres", "csv"})


def _skip_review_flagged_llm() -> bool:
    return str(os.environ.get("HP_CATALOG_SKIP_REVIEW_FLAGGED_LLM", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _min_llm_catalog_confidence() -> float:
    raw = os.environ.get("HP_LLM_MIN_CONFIDENCE", "").strip()
    if not raw:
        return 0.72
    try:
        return float(raw)
    except ValueError:
        return 0.72


_hp_index_cache_key: Tuple[int, float] | None = None
_hp_observed_idx: Dict[str, int] = {}
_hp_llm_ok_idx: Dict[str, int] = {}


def invalidate_hp_catalog_cache() -> None:
    """Принудительно сбросить индекс (тесты, скрипт сразу после fill)."""
    global _hp_index_cache_key
    _hp_index_cache_key = None


def _hp_catalog_mtime_key() -> Optional[Tuple[int, float]]:
    if not HP_CATALOG_DB_PATH.is_file():
        return None
    st = HP_CATALOG_DB_PATH.stat()
    # st_mtime может быть float; ns точнее для быстрых последовательных записей.
    return (int(st.st_mtime_ns), float(st.st_mtime))


def _rebuild_hp_catalog_indices() -> Tuple[Dict[str, int], Dict[str, int]]:
    observed: Dict[str, int] = {}
    llm_ok: Dict[str, int] = {}
    min_c = _min_llm_catalog_confidence()
    if not HP_CATALOG_DB_PATH.is_file():
        return observed, llm_ok
    try:
        from hp_catalog_store import connect as hp_connect_catalog
        from hp_catalog_store import ensure_schema as hp_ensure_hp_catalog_schema

        conn = hp_connect_catalog(HP_CATALOG_DB_PATH)
        try:
            hp_ensure_hp_catalog_schema(conn)
            rows = conn.execute(
                """
                SELECT
                    norm_manufacturer, norm_model, norm_version, norm_engine_type,
                    displacement_cc, year_month, power_hp, source, llm_status, llm_confidence,
                    COALESCE(review_flag, 0) AS review_flag
                FROM hp_catalog
                WHERE power_hp IS NOT NULL AND power_hp > 0 AND llm_status = 'done'
                """
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return observed, llm_ok
    skip_rf = _skip_review_flagged_llm()
    for (
        nm,
        nmd,
        nv,
        net,
        dcc,
        ym,
        hp,
        source,
        _ls,
        conf,
        review_flag,
    ) in rows:
        try:
            hpv = int(hp)
        except (TypeError, ValueError):
            continue
        if not (20 <= hpv <= 2500):
            continue
        src = str(source or "").strip().lower()
        keys = _hp_catalog_keys(
            nm=str(nm or ""),
            nmd=str(nmd or ""),
            nv=str(nv or ""),
            net=str(net or ""),
            dcc=str(int(dcc)) if dcc not in (None, "") else "",
            ym=str(ym or ""),
        )
        tgt: Dict[str, int]
        if src in HP_CATALOG_OBSERVED_SOURCES:
            tgt = observed
        else:
            try:
                rfv = int(review_flag or 0)
            except (TypeError, ValueError):
                rfv = 0
            if skip_rf and rfv != 0:
                continue
            if conf is not None:
                try:
                    c = float(conf)
                except (TypeError, ValueError):
                    c = -1.0
                if c < min_c:
                    continue
            # conf IS NULL → старые записи каталога (до столбца) остаются видимыми.
            tgt = llm_ok
        for k in keys:
            tgt.setdefault(k, hpv)
    return observed, llm_ok


def _load_hp_catalog_indices() -> Tuple[Dict[str, int], Dict[str, int]]:
    global _hp_index_cache_key, _hp_observed_idx, _hp_llm_ok_idx
    key = _hp_catalog_mtime_key()
    if key is None:
        _hp_index_cache_key = None
        _hp_observed_idx = {}
        _hp_llm_ok_idx = {}
        return {}, {}
    if _hp_index_cache_key == key:
        return _hp_observed_idx, _hp_llm_ok_idx
    observed, llm_ok = _rebuild_hp_catalog_indices()
    _hp_index_cache_key = key
    _hp_observed_idx = observed
    _hp_llm_ok_idx = llm_ok
    return observed, llm_ok


def _norm(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip()).lower()


def _norm_key(s: Any) -> str:
    return _NON_WORD_RE.sub("", _norm(s))


def _norm_disp(disp: Any) -> str:
    if disp is None or disp == "":
        return ""
    try:
        n = int(re.sub(r"\D", "", str(disp)))
        if 500 <= n <= 8000:
            return str(n)
    except ValueError:
        pass
    return ""


def _norm_ym(value: Any) -> str:
    if value is None:
        return ""
    digits = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if len(digits) >= 6:
        return digits[:6]
    if len(digits) == 4:
        return f"{digits}01"
    return ""


def _year_to_ym_candidates(value: str) -> List[str]:
    if not value:
        return []
    if len(value) == 4:
        return [f"{value}{m:02d}" for m in range(1, 13)]
    if len(value) == 6:
        return [value]
    return []


def _version_candidates(car_data: Dict[str, Any]) -> List[str]:
    vals: List[str] = []
    for key in ("gradeName", "generation", "configuration", "trim_name", "version"):
        v = _norm_key(car_data.get(key))
        if v and v not in vals:
            vals.append(v)
    return vals


def _load_power_lookup() -> List[Dict[str, Any]]:
    if not POWER_LOOKUP_PATH.exists():
        return []
    try:
        with open(POWER_LOOKUP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _hp_catalog_keys(*, nm: str, nmd: str, nv: str, net: str, dcc: str, ym: str) -> Tuple[str, ...]:
    """Ключи приоритета: от точного к мягкому."""
    return (
        f"{nm}|{nmd}|{nv}|{net}|{dcc}|{ym}",
        f"{nm}|{nmd}|{nv}|{net}|{dcc}|",
        f"{nm}|{nmd}||{net}|{dcc}|{ym}",
        f"{nm}|{nmd}||{net}|{dcc}|",
        f"{nm}|{nmd}|||{dcc}|{ym}",
        f"{nm}|{nmd}|||{dcc}|",
    )


def _scan_index(idx: Dict[str, int], car_data: Dict[str, Any]) -> Optional[int]:
    if not idx:
        return None
    nm = _norm_key(car_data.get("mark") or car_data.get("manufacturer") or car_data.get("manufacturerName"))
    nmd = _norm_key(car_data.get("model") or car_data.get("modelName"))
    if not nm or not nmd:
        return None
    net = _norm_key(car_data.get("engine_type") or car_data.get("fuel") or car_data.get("engineType"))
    dcc = _norm_disp(car_data.get("displacement") or car_data.get("displacement_cc") or car_data.get("engine_volume"))
    ym = _norm_ym(car_data.get("yearMonth") or car_data.get("year_month") or car_data.get("year"))
    yms = _year_to_ym_candidates(ym) if ym else [""]
    versions = _version_candidates(car_data) or [""]
    for v in versions:
        for ymv in yms:
            for key in _hp_catalog_keys(nm=nm, nmd=nmd, nv=v, net=net, dcc=dcc, ym=ymv):
                hp = idx.get(key)
                if hp is not None:
                    return hp
    return None


def _hp_catalog_lookup_observed(car_data: Dict[str, Any]) -> Optional[int]:
    observed, _ = _load_hp_catalog_indices()
    return _scan_index(observed, car_data)


def _hp_catalog_lookup_llm(car_data: Dict[str, Any]) -> Optional[int]:
    _, llm_ok = _load_hp_catalog_indices()
    return _scan_index(llm_ok, car_data)


def _motor_vin_for_hp_catalog(car_data: Dict[str, Any]) -> Tuple[str, str]:
    """motor_code_norm + верхний регистр vin prefix (до 11 символов) для OEM-правил."""
    from hp_catalog_store import normalize_key_part

    try:
        from engine_hp_resolver import extract_motor_code
    except ImportError:
        extract_motor_code = None

    motor_raw = ""
    candidates: List[Optional[dict]] = []
    if isinstance(car_data, dict):
        candidates.append(car_data)
        inner = car_data.get("data")
        if isinstance(inner, dict):
            candidates.append(inner)

    if extract_motor_code is not None:
        for blob in candidates:
            if isinstance(blob, dict):
                m = extract_motor_code(blob)
                if m:
                    motor_raw = m
                    break

    motor_n = normalize_key_part(motor_raw) if motor_raw else ""

    vin = ""
    for blob in candidates:
        if isinstance(blob, dict) and blob.get("vin"):
            vin = str(blob.get("vin") or "").strip().upper()
            break
    vin_pf = vin[:11] if vin else ""
    return motor_n, vin_pf


def _enqueue_hp_catalog_pending(car_data: Dict[str, Any]) -> None:
    """Регистрирует пропуск в hp_catalog для фонового LLM-филла."""
    if not HP_CATALOG_DB_PATH.parent.exists():
        return
    manufacturer = str(car_data.get("mark") or car_data.get("manufacturer") or car_data.get("manufacturerName") or "").strip()
    model = str(car_data.get("model") or car_data.get("modelName") or "").strip()
    if not manufacturer or not model:
        return
    version = str(
        car_data.get("gradeName")
        or car_data.get("generation")
        or car_data.get("configuration")
        or car_data.get("trim_name")
        or ""
    ).strip()
    engine_type = str(car_data.get("engine_type") or car_data.get("fuel") or car_data.get("engineType") or "").strip()
    displacement_cc = _norm_disp(car_data.get("displacement") or car_data.get("displacement_cc") or car_data.get("engine_volume"))
    year_month = _norm_ym(car_data.get("yearMonth") or car_data.get("year_month") or car_data.get("year"))
    motor_n, vin_pf = _motor_vin_for_hp_catalog(car_data)
    try:
        from hp_catalog_store import connect as hp_connect_catalog
        from hp_catalog_store import ensure_schema as hp_ensure_hp_catalog_schema

        conn = hp_connect_catalog(HP_CATALOG_DB_PATH)
        try:
            hp_ensure_hp_catalog_schema(conn)
            conn.execute(
                """
                INSERT INTO hp_catalog (
                    manufacturer, model, version, engine_type, displacement_cc, drive, year_month,
                    norm_manufacturer, norm_model, norm_version, norm_engine_type,
                    motor_code_norm, vin_prefix,
                    llm_status, source
                ) VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, 'pending', 'catalog')
                ON CONFLICT(norm_manufacturer, norm_model, norm_version, norm_engine_type, COALESCE(displacement_cc, -1), year_month)
                DO UPDATE SET
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now'),
                    motor_code_norm = COALESCE(NULLIF(excluded.motor_code_norm, ''), hp_catalog.motor_code_norm),
                    vin_prefix = COALESCE(NULLIF(excluded.vin_prefix, ''), hp_catalog.vin_prefix)
                """,
                (
                    manufacturer,
                    model,
                    version,
                    engine_type,
                    int(displacement_cc) if displacement_cc else None,
                    year_month,
                    _norm_key(manufacturer),
                    _norm_key(model),
                    _norm_key(version),
                    _norm_key(engine_type),
                    motor_n,
                    vin_pf,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        return


def get_power_from_lookup(car_data: Dict[str, Any]) -> Optional[int]:
    """
    Мощность из локальной базы data/power_lookup.json.
    Формат: список объектов с полями make, model, year, displacement (опционально), power.
    """
    entries = _load_power_lookup()
    if not entries:
        return None
    make = _norm(car_data.get("mark") or car_data.get("manufacturer") or car_data.get("manufacturerName") or "")
    model = _norm(car_data.get("model") or car_data.get("modelName") or "")
    year = car_data.get("year") or car_data.get("yearMonth") or ""
    if year:
        year = str(year).strip()[:4]
    disp = _norm_disp(car_data.get("displacement"))
    if not make and not model:
        return None
    for e in entries:
        e_make = _norm(e.get("make") or e.get("brand") or "")
        e_model = _norm(e.get("model") or "")
        e_year = str(e.get("year") or "").strip()[:4]
        e_disp = _norm_disp(e.get("displacement"))
        e_power = e.get("power") or e.get("horsepower") or e.get("hp")
        if e_power is None:
            continue
        try:
            hp = int(e_power)
        except (TypeError, ValueError):
            continue
        if not (20 <= hp <= 2000):
            continue
        if e_make and make and e_make not in make and make not in e_make:
            continue
        if e_model and model and e_model not in model and model not in e_model:
            continue
        if e_year and year and e_year != year:
            continue
        if e_disp and disp and e_disp != disp:
            continue
        return hp
    return None


def get_power_for_car(
    car_data: Dict[str, Any],
    *,
    record_source: bool = False,
) -> Optional[int]:
    """
    Получить мощность (л.с.): данные карточки → observed hp_catalog → engine_map →
    LLM hp_catalog (confidence) → power_lookup.json; иначе pending.

    При record_source=True выставляет power_source / power_estimated.
    """
    if not isinstance(car_data, dict):
        return None
    if car_data.get("power") and str(car_data.get("power", "")).strip():
        try:
            return int(re.sub(r"\D", "", str(car_data["power"])))
        except ValueError:
            pass

    hp_catalog_obs = _hp_catalog_lookup_observed(car_data)
    if hp_catalog_obs is not None:
        if record_source:
            car_data.setdefault("power_source", "hp_catalog_observed")
        return hp_catalog_obs

    try:
        from engine_hp_resolver import resolve_engine_hp

        hp_map = resolve_engine_hp(car_data, record_source=record_source)
        if hp_map is not None:
            return hp_map
    except ImportError:
        pass

    hp_catalog_llm = _hp_catalog_lookup_llm(car_data)
    if hp_catalog_llm is not None:
        if record_source:
            car_data.setdefault("power_source", "hp_catalog_llm")
            car_data["power_estimated"] = True
        return hp_catalog_llm

    hp_lookup = get_power_from_lookup(car_data)
    if hp_lookup is not None:
        if record_source:
            car_data.setdefault("power_source", "power_lookup")
        return hp_lookup

    _enqueue_hp_catalog_pending(car_data)
    return None

