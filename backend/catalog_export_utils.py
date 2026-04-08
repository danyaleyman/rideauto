"""Утилиты нормализации каталога для postgres_catalog_sync и связанных скриптов."""
from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Iterator

from encar_image_order import _sort_encar_image_url_list, _sort_h_images_list_entries


def fill_power_from_external(data: dict) -> None:
    if not isinstance(data, dict):
        return
    if data.get("power") and str(data.get("power", "")).strip():
        return
    try:
        from power_from_external import get_power_for_car

        hp = get_power_for_car(data, record_source=True)
        if hp is not None:
            data["power"] = str(hp)
    except ImportError:
        pass


def write_json_atomic(path: Path, payload: dict, gzip_enabled: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    if gzip_enabled:
        gz_path = Path(str(path) + ".gz")
        gz_tmp = gz_path.with_name(gz_path.name + ".tmp")
        try:
            with gzip.open(gz_tmp, "wt", encoding="utf-8") as gz:
                json.dump(payload, gz, ensure_ascii=False)
            gz_tmp.replace(gz_path)
        finally:
            if gz_tmp.exists():
                try:
                    gz_tmp.unlink()
                except OSError:
                    pass


def iter_chunks(items: list, chunk_size: int) -> Iterator[tuple[int, list]]:
    for i in range(0, len(items), chunk_size):
        yield i // chunk_size + 1, items[i : i + chunk_size]


def listing_key_for_export(car_id: str, payload: dict) -> str:
    raw = payload.get("data") if isinstance(payload.get("data"), dict) else None
    d = raw if isinstance(raw, dict) else payload
    inner = str((d or {}).get("inner_id") or "").strip()
    if inner:
        return f"i:{inner}"
    return f"c:{car_id}"


def normalize_car_media_fields(car: dict) -> None:
    data = car.get("data")
    if not isinstance(data, dict):
        return
    raw_im = data.get("images")
    if isinstance(raw_im, str):
        try:
            arr = json.loads(raw_im)
        except Exception:
            arr = None
        if isinstance(arr, list):
            s = _sort_encar_image_url_list([x for x in arr if isinstance(x, str)])
            data["images"] = json.dumps(s, ensure_ascii=False)
    elif isinstance(raw_im, list):
        s = _sort_encar_image_url_list([x for x in raw_im if isinstance(x, str)])
        data["images"] = s
    raw_h = data.get("h_images")
    if isinstance(raw_h, str):
        try:
            arr = json.loads(raw_h)
        except Exception:
            arr = None
        if isinstance(arr, list):
            s = _sort_h_images_list_entries([x for x in arr if isinstance(x, dict)])
            data["h_images"] = json.dumps(s, ensure_ascii=False)
    elif isinstance(raw_h, list):
        s = _sort_h_images_list_entries([x for x in raw_h if isinstance(x, dict)])
        data["h_images"] = s
