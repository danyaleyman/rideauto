"""Линейка модели (кластер) для фасета Meilisearch: эвристика + опциональный JSON с явными совпадениями."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RULES_PATH = _REPO_ROOT / "data" / "model_cluster_rules.json"

_STRIP_PATTERNS: tuple[str, ...] = (
    r"(?is)\s+(?:plug-in\s+hybrid|hybrid|hev|phev|mhev|ev)\s*$",
    r"(?is)\s+(?:AD|XD)\b\s*$",
    r"(?is)\s+\d{4}\s*$",
)


def _norm_brand_key(brand: str) -> str:
    return " ".join((brand or "").strip().lower().split())


def _norm_model_group_key(mg: str) -> str:
    return " ".join((mg or "").strip().lower().split())


def _heuristic_strip(mg: str) -> str:
    s = (mg or "").strip()
    if not s:
        return ""
    prev = None
    work = s
    while prev != work:
        prev = work
        for pat in _STRIP_PATTERNS:
            work = re.sub(pat, "", work).strip()
    return work or s


@lru_cache(maxsize=64)
def load_model_cluster_rules(path: Optional[str] = None) -> Mapping[str, Any]:
    fp = Path(path) if path else _DEFAULT_RULES_PATH
    if not fp.is_file():
        return {}
    try:
        raw = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def compute_model_cluster(
    brand: str,
    model_group: str,
    *,
    rules_path: Optional[str] = None,
) -> str:
    """
    Возвращает короткую линейку для склейки вариантов (Avante / Avante AD / …).
    При пустом — пустая строка (синк подставит model_group).
    """
    mg = (model_group or "").strip()
    if not mg:
        return ""
    rules = load_model_cluster_rules(rules_path)
    bkey = _norm_brand_key(brand)
    mgkey = _norm_model_group_key(mg)

    explicit_any: Dict[str, str] = {}
    ea = rules.get("explicit_any_brand") if isinstance(rules.get("explicit_any_brand"), dict) else {}
    for rk, rv in ea.items():
        if isinstance(rk, str) and isinstance(rv, str):
            explicit_any[_norm_model_group_key(rk)] = rv.strip()

    by_brand = rules.get("by_brand") if isinstance(rules.get("by_brand"), dict) else {}
    if bkey:
        slab = by_brand.get(bkey)
        if isinstance(slab, dict):
            for rk, rv in slab.items():
                if isinstance(rk, str) and isinstance(rv, str):
                    explicit_any[_norm_model_group_key(rk)] = rv.strip()

        for alt in (brand or "").strip().lower().replace("-", " ").split():
            slab2 = by_brand.get(alt)
            if isinstance(slab2, dict):
                for rk, rv in slab2.items():
                    if isinstance(rk, str) and isinstance(rv, str):
                        explicit_any[_norm_model_group_key(rk)] = rv.strip()

    hit = explicit_any.get(mgkey)
    if isinstance(hit, str) and hit.strip():
        return hit.strip()

    stripped = _heuristic_strip(mg)
    return stripped if stripped else mg
