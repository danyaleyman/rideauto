"""Точечный KO→EN по data/encar_mapping.json для заголовков Encar (дополняет facet_canonical_english)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MAPPING_PATH = _REPO_ROOT / "data" / "encar_mapping.json"


def _encar_section_for_field(field: str) -> str:
    f = (field or "").strip().lower()
    if f in ("trim_name", "grade", "gradename", "trim"):
        return "trim"
    if f in ("configuration", "generation", "type"):
        return "generation"
    if f == "modelgroupname":
        return "model"
    if f in ("mark", "model", "generation", "type", "trim"):
        return f
    return "model"


@lru_cache(maxsize=1)
def _load_mapping_sections() -> Dict[str, Dict[str, str]]:
    if not _MAPPING_PATH.is_file():
        return {}
    try:
        raw = json.loads(_MAPPING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: Dict[str, Dict[str, str]] = {}
    for key in ("mark", "model", "generation", "type", "trim"):
        m = raw.get(key)
        if not isinstance(m, dict):
            continue
        out[key] = {str(k).strip(): str(v).strip() for k, v in m.items() if str(k).strip() and str(v).strip()}
    return out


def encar_mapping_en_for(field: str, ko_text: object) -> str:
    s = str(ko_text or "").strip()
    if not s:
        return ""
    sect = _encar_section_for_field(field)
    maps = _load_mapping_sections()
    table = maps.get(sect) or {}
    hit = table.get(s)
    if hit:
        return hit
    if sect != "type":
        hit = maps.get("type", {}).get(s)
        if hit:
            return hit
    return ""
