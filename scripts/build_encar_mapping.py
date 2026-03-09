# -*- coding: utf-8 -*-
"""
Читает data/encar_api_flat_for_mapping.csv и строит data/encar_mapping.json
для фронта: KO -> EN по категориям mark, model, generation, type, trim.
Первый встреченный EN для каждого KO сохраняется.
"""
from pathlib import Path
import csv
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CSV_PATH = DATA_DIR / "encar_api_flat_for_mapping.csv"
OUT_PATH = DATA_DIR / "encar_mapping.json"


def main():
    if not CSV_PATH.exists():
        print("CSV not found:", CSV_PATH)
        print("Run first: python scripts/encar_fetch_tree.py")
        return 1

    mapping = {
        "mark": {},
        "model": {},
        "generation": {},
        "type": {},
        "trim": {},
    }
    # CSV: brand, brand_en, model, model_en, generation, generation_en, type, type_en, trim, trim_en
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            def add(cat: str, ko_key: str, en_val: str):
                ko = (ko_key or "").strip()
                en = (en_val or "").strip()
                if not ko:
                    return
                if ko not in mapping[cat] and en:
                    mapping[cat][ko] = en
                elif ko not in mapping[cat]:
                    mapping[cat][ko] = ko

            add("mark", row.get("brand"), row.get("brand_en"))
            add("model", row.get("model"), row.get("model_en"))
            add("generation", row.get("generation"), row.get("generation_en"))
            add("type", row.get("type"), row.get("type_en"))
            add("trim", row.get("trim"), row.get("trim_en"))

    DATA_DIR.mkdir(exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print("Saved:", OUT_PATH)
    for k, v in mapping.items():
        print("  %s: %d entries" % (k, len(v)))
    return 0


if __name__ == "__main__":
    exit(main())
