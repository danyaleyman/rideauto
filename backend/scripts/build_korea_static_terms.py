# -*- coding: utf-8 -*-
"""
Собирает data/korea_static_terms.json из GPT-выгрузок (как one.json / two.json).

- category \"make\" → домен \"mark\" (как в карточке Encar и localize_car_data).
- fuel_type из two.json → ru.engine_type (в БД топливо лежит в engine_type).
- drive_type: дублируется в prep_drive_type для домена синка.

Ночной encar / build_encar_mapping.py этот файл НЕ трогает — только этот скрипт.
Запуск из корня репозитория (пути к вашим GPT-файлам):

  python backend/scripts/build_korea_static_terms.py --one path/to/one.json --two path/to/two.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_OUT = DATA_DIR / "korea_static_terms.json"


def _norm_category_one(cat: str) -> str:
    c = (cat or "").strip()
    if c == "make":
        return "mark"
    return c


def build(one_path: Path, two_path: Path) -> dict:
    one = json.loads(one_path.read_text(encoding="utf-8"))
    two = json.loads(two_path.read_text(encoding="utf-8"))
    en: dict[str, dict[str, str]] = {}
    ru: dict[str, dict[str, str]] = {}

    for row in one:
        if not isinstance(row, dict):
            continue
        cat = _norm_category_one(str(row.get("category") or ""))
        orig = str(row.get("original") or "").strip()
        eng = str(row.get("english") or "").strip()
        if not orig or not eng:
            continue
        en.setdefault(cat, {})[orig] = eng

    for row in two:
        if not isinstance(row, dict):
            continue
        cat = str(row.get("category") or "").strip()
        orig = str(row.get("original") or "").strip()
        rus = str(row.get("russian") or "").strip()
        if not orig or not rus:
            continue
        if cat == "fuel_type":
            cat = "engine_type"
        ru.setdefault(cat, {})[orig] = rus

    if "drive_type" in ru:
        ru["prep_drive_type"] = dict(ru["drive_type"])
    if "drive_type" in en:
        en["prep_drive_type"] = dict(en["drive_type"])

    return {"version": 1, "en": en, "ru": ru}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--one", type=Path, required=True, help="JSON: make→mark, model, generation + english")
    p.add_argument("--two", type=Path, required=True, help="JSON: fuel/body/color/drive + russian")
    p.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    if not args.one.is_file() or not args.two.is_file():
        print("Файлы не найдены:", args.one, args.two)
        return 1
    out = build(args.one, args.two)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved:", args.out)
    for lang, block in ("en", out["en"]), ("ru", out["ru"]):
        print(f"  {lang}:", {k: len(v) for k, v in block.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
