#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собирает data/china_static_terms.json из GPT-выгрузки china mapping.json.

Ожидаемый формат входа:
{
  "marks": [{"original": "...", "translated": "..."}],
  "models": [...],
  "generations": [...],
  "trim_names": [...],
  "transmissions": [...],
  "colors": [...],
  "drive_types": [...],
  "fuel_types": [...]
}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUT = DATA_DIR / "china_static_terms.json"


def _as_str(v: object) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _load_pairs(src: dict, key: str) -> dict[str, str]:
    out: dict[str, str] = {}
    rows = src.get(key)
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        original = _as_str(row.get("original"))
        translated = _as_str(row.get("translated"))
        if not original or not translated:
            continue
        out[original] = translated
    return out


def build(source_path: Path) -> dict:
    src = json.loads(source_path.read_text(encoding="utf-8"))

    en: dict[str, dict[str, str]] = {}
    ru: dict[str, dict[str, str]] = {}

    en["mark"] = _load_pairs(src, "marks")
    en["model"] = _load_pairs(src, "models")
    en["generation"] = _load_pairs(src, "generations")
    trim = _load_pairs(src, "trim_names")
    en["trim_name"] = dict(trim)
    en["configuration"] = dict(trim)
    en["gradeName"] = dict(trim)

    ru["transmission_type"] = _load_pairs(src, "transmissions")
    ru["color"] = _load_pairs(src, "colors")
    ru["drive_type"] = _load_pairs(src, "drive_types")
    ru["prep_drive_type"] = dict(ru["drive_type"])
    ru["engine_type"] = _load_pairs(src, "fuel_types")

    return {"version": 1, "en": en, "ru": ru}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True, help="Path to china mapping.json")
    p.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()

    if not args.source.is_file():
        print("Файл не найден:", args.source)
        return 1

    out = build(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", args.out)
    for lang, block in ("en", out["en"]), ("ru", out["ru"]):
        print(f"  {lang}:", {k: len(v) for k, v in block.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
