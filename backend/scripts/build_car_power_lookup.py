# -*- coding: utf-8 -*-
"""
Строит data/car_power_lookup.json из data/encar_api_flat_for_mapping.csv:
извлекает мощность (л.с.) из полей generation, type, trim (например "150마력", " (180hp)")
и формирует lookup для подстановки в парсере, когда power пустой.

Ключ: "brand|model|value" (value = generation или type или trim с ма력).
Использование: python scripts/build_car_power_lookup.py
"""
import csv
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
CSV_PATH = DATA_DIR / "encar_api_flat_for_mapping.csv"
OUT_PATH = DATA_DIR / "car_power_lookup.json"


def extract_power(s: str) -> int | None:
    """Только явные указания мощности: N마력 или N hp. Не (992) — это поколение."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    m = re.search(r'\(?\s*(\d{2,4})\s*\)?\s*마력', s)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d{2,4})\s*hp\b', s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def main():
    if not CSV_PATH.exists():
        print("CSV not found:", CSV_PATH)
        return 1
    lookup = {}
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            brand = (row.get("brand") or "").strip()
            model = (row.get("model") or "").strip()
            if not brand:
                continue
            for field in ("generation", "type", "trim"):
                val = (row.get(field) or "").strip()
                if not val:
                    continue
                pw = extract_power(val)
                if pw is None:
                    continue
                key = f"{brand}|{model}|{val}"
                if key not in lookup or lookup[key] < pw:
                    lookup[key] = pw
                # короткий ключ без варианта комплектации (только generation/type)
                short = f"{brand}|{model}|{val.split('|')[0].strip()}" if "|" in val else key
                if short not in lookup or lookup[short] < pw:
                    lookup[short] = pw
    DATA_DIR.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(lookup, f, ensure_ascii=False, indent=0)
    print("Saved:", OUT_PATH, "(%d keys)" % len(lookup))
    return 0


if __name__ == "__main__":
    exit(main())
