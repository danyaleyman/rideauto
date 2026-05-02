"""Единый справочник топливных подписей: data/fuel_label_aliases.json (см. web sync-static-data)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict

_REPO_DATA = Path(__file__).resolve().parent.parent / "data"
_FUEL_JSON = _REPO_DATA / "fuel_label_aliases.json"
_WS_RE = re.compile(r"\s+")


def _fuel_plus_norm(s: str) -> str:
    return _WS_RE.sub(" ", str(s).replace("+", " + ").replace("  ", " ").strip())


def _norm_lookup_key(raw: str) -> str:
    s = _WS_RE.sub(" ", str(raw).strip()).lower()
    return s


@lru_cache(maxsize=1)
def fuel_to_canonical_ru_flat() -> Dict[str, str]:
    """Прямые ключи как в файле → канон Ru (дубликаты ключей недопустимы в JSON)."""
    if not _FUEL_JSON.is_file():
        return {}
    try:
        data = json.loads(_FUEL_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw = data.get("to_canonical_ru") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        kk = k.strip()
        vv = v.strip()
        if not kk or not vv:
            continue
        out[kk] = vv
    return out


@lru_cache(maxsize=1)
def fuel_to_canonical_ru_normalized() -> Dict[str, str]:
    """Ускорение: ключ в lower/collapsed-ws → канон (последний выигрывает при конфликте форм записи)."""
    flat = fuel_to_canonical_ru_flat()
    merged: Dict[str, str] = {}
    for k, v in flat.items():
        merged[_norm_lookup_key(k)] = v
    return merged


def fuel_alias_resolve(text: object) -> str:
    """Сырая строка топлива (KO/RU/EN/смесь) → канон Ru из JSON; пустая строка если нет попадания."""
    s = "" if text is None else str(text).strip()
    if not s:
        return ""
    flat = fuel_to_canonical_ru_flat()
    nmap = fuel_to_canonical_ru_normalized()
    plus = _fuel_plus_norm(s)
    for cand in (s, plus):
        if cand in flat:
            return flat[cand]
        hit = nmap.get(_norm_lookup_key(cand), "")
        if hit:
            return hit
    return ""


def canonicalize_fuel_label_ru(text: object) -> str:
    """Обратная совместимость: то же, что fuel_alias_resolve (исторически только lower-key lookup)."""
    return fuel_alias_resolve(text)
