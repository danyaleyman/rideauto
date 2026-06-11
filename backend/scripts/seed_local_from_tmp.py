#!/usr/bin/env python3
"""Загрузить демо-каталог из tmp_*.json (Китай) + синтетика Encar для локальной разработки."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from catalog_pg_upsert import upsert_json_batch

DSN = "postgresql://wra:wra@127.0.0.1:5433/wra"

# mark, model, trim, year, km, price_won (만원 = 10k KRW, как в Encar API), fuel, cc, hp
ENCAR_SAMPLES: list[tuple] = [
    ("encar-41877280", "Kia", "EV6", "GT-Line AWD", 2022, 45000, 4850, "electric", None, 325),
    ("encar-41900001", "Hyundai", "Sonata", "DN8", 2021, 62000, 2250, "gasoline", 1999, 180),
    ("encar-41900002", "Hyundai", "Tucson", "NX4", 2023, 28000, 3100, "gasoline", 1598, 180),
    ("encar-41900003", "Genesis", "G80", "RG3", 2020, 88000, 4200, "gasoline", 2999, 304),
    ("encar-41900004", "BMW", "520i", "G30", 2019, 71000, 2800, "gasoline", 1998, 184),
    ("encar-41900005", "Mercedes-Benz", "E220d", "W213", 2018, 95000, 2650, "diesel", 1950, 194),
    ("encar-41900006", "Toyota", "Camry", "XV70", 2021, 54000, 2400, "gasoline", 2487, 181),
    ("encar-41900007", "Kia", "K5", "DL3", 2022, 41000, 2150, "gasoline", 1999, 180),
    ("encar-41900008", "Hyundai", "Palisade", "LX3", 2023, 35000, 5200, "gasoline", 3470, 272),
    ("encar-41900009", "Audi", "A6", "C8", 2020, 67000, 3850, "gasoline", 1984, 190),
    # +7 Sonata для локального теста price-benchmark (min 8 в когорте mark+model)
    ("encar-41900101", "Hyundai", "Sonata", "DN8", 2020, 78000, 1980, "gasoline", 1999, 180),
    ("encar-41900102", "Hyundai", "Sonata", "DN8", 2021, 55000, 2120, "gasoline", 1999, 180),
    ("encar-41900103", "Hyundai", "Sonata", "DN8", 2022, 42000, 2350, "gasoline", 1999, 180),
    ("encar-41900104", "Hyundai", "Sonata", "DN8", 2019, 91000, 1750, "gasoline", 1999, 180),
    ("encar-41900105", "Hyundai", "Sonata", "DN8", 2023, 31000, 2580, "gasoline", 1999, 180),
    ("encar-41900106", "Hyundai", "Sonata", "DN8", 2020, 68000, 2010, "gasoline", 1999, 180),
    ("encar-41900107", "Hyundai", "Sonata", "DN8", 2021, 59000, 2290, "gasoline", 1999, 180),
]

_FUEL_KO = {
    "gasoline": "가솔린",
    "diesel": "디젤",
    "electric": "전기",
}


# Стабильные фото авто (Unsplash Source — без API-ключа, hotlink OK для dev).
# Лицензия Unsplash: https://unsplash.com/license (для prod — атрибуция или свой CDN).
_UNSPLASH_CAR_PHOTOS = (
    "photo-1494976388531-d1058494cdd8",  # Ford Mustang
    "photo-1544636331-e26879cd4d9b",  # sedan
    "photo-1503376780353-7e6692767b70",  # Porsche
    "photo-1552510917-e7e238877658",  # Chevrolet Camaro
    "photo-1583121274702-24b019f9c0ec",  # BMW
    "photo-1606664515524-ed2f7862720f",  # SUV
    "photo-1618843479313-40f8afb3140a",  # Mercedes
    "photo-1619767886558-efdc259cde1a",  # Tesla
    "photo-1621007947382-b76b3340fabc",  # Toyota
    "photo-1616422285627-1eb4466e7572",  # Kia-style crossover
    "photo-1609521263047-f8f205293bb4",  # Audi
    "photo-1553440569-bcc63801a86d",  # Hyundai-style
    "photo-1617788138017-80ad10651351",  # Genesis-style
    "photo-1590362899447-42b741ae21bb",  # sedan white
    "photo-1533473359331-0135ef1b58bf",  # road car
    "photo-148529157115f-9fe79543c080",  # classic
    "photo-1502877338535-766e1452684a",  # family car
)


def _demo_image_url(cid: str, _mark: str, _model: str, offset: int = 0) -> str:
    """Dev-only: Unsplash CDN (не picsum — часто 403). Prod — Encar/Che168 URL из парсера."""
    idx = (sum(ord(c) for c in cid) + offset) % len(_UNSPLASH_CAR_PHOTOS)
    photo = _UNSPLASH_CAR_PHOTOS[idx]
    return (
        f"https://images.unsplash.com/{photo}"
        f"?w=1200&h=800&fit=crop&q=80&auto=format"
    )


def _demo_gallery_urls(cid: str, mark: str, model: str, count: int = 5) -> list[str]:
    """Несколько кадров — галерея Encar (главное + боковые миниатюры)."""
    return [_demo_image_url(cid, mark, model, i) for i in range(count)]


def _load_car_json(path: Path) -> tuple[str, dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "result" in raw and isinstance(raw["result"], dict):
        r = raw["result"]
        cid = str(r.get("id") or r.get("data", {}).get("id") or path.stem)
        data = r.get("data") if isinstance(r.get("data"), dict) else r
    elif "result" in raw and isinstance(raw["result"], list) and raw["result"]:
        item = raw["result"][0]
        cid = str(item.get("id") or item.get("data", {}).get("id"))
        data = item.get("data") if isinstance(item.get("data"), dict) else item
    else:
        raise ValueError(f"unsupported shape: {path}")
    if "id" not in data:
        data["id"] = cid
    data["source"] = data.get("source") or ("che168" if cid.startswith("che168") else "encar")
    return cid, data


def _encar_payload(
    cid: str,
    mark: str,
    model: str,
    trim: str,
    year: int,
    km: int,
    price_won: int,  # 만원
    fuel: str,
    cc: int | None,
    hp: int | None,
) -> dict:
    fuel_ko = _FUEL_KO.get(fuel, "가솔린")
    spec: dict = {
        "engine_type": fuel_ko,
        "mileage_km": str(km),
        "color": "White",
    }
    if cc:
        spec["displacement_cc"] = str(cc)
    if hp:
        spec["power_hp"] = str(hp)

    return {
        "id": cid,
        "source": "encar",
        "mark": mark,
        "model": model,
        "gradeName": trim,
        "modelGroupName": model,
        "year": year,
        "yearMonth": year * 100 + 6,
        "km_age": km,
        "mileage": km,
        # Encar list price в 만원 (×10 000 KRW) — без этого sync ставит price_on_request.
        "price_won": price_won,
        "engine_type": fuel_ko,
        **({"displacement_cc": cc} if cc else {}),
        **({"power_hp": hp} if hp else {}),
        "images": _demo_gallery_urls(cid, mark, model),
        "condition_clean": {
            "insurance_cases": 0,
            "damaged_parts_count": 0,
            "insurance_payout_krw": 0,
        },
        "spec_clean": spec,
        "identity_clean": {"mark": mark, "model": model, "year": str(year), "trim_name": trim},
    }


def main() -> int:
    batch: list[tuple[str, str]] = []
    china = 0
    for p in (ROOT / "tmp_car.json", ROOT / "tmp_bmw.json", ROOT / "tmp_corolla.json"):
        if p.is_file():
            cid, data = _load_car_json(p)
            batch.append((cid, json.dumps(data, ensure_ascii=False)))
            china += 1
    for args in ENCAR_SAMPLES:
        cid = args[0]
        data = _encar_payload(*args)
        batch.append((cid, json.dumps(data, ensure_ascii=False)))
    n = upsert_json_batch(DSN, batch)
    print(f"seeded {n} cars (china={china}, encar={len(ENCAR_SAMPLES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
