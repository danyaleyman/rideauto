"""Упорядочивание медиа каталога: Encar по кадру + экстерьер→интерьер; Китай без лексической пересортировки."""
from __future__ import annotations

import json
from typing import Any, List

from encar_image_order import _sort_encar_image_url_list


def catalog_data_is_encar(data: dict) -> bool:
    src = str((data or {}).get("source") or "").strip().lower()
    if src in ("che168", "china"):
        return False
    cid = str((data or {}).get("id") or "").strip().lower()
    if cid.startswith("che168-"):
        return False
    return src in ("", "encar")


def order_image_urls_for_catalog(urls: List[str], *, encar: bool) -> List[str]:
    """Плоский список URL: Encar — по номеру кадра; иначе стабильно с дедупом (порядок источника)."""
    if encar:
        return _sort_encar_image_url_list([u for u in urls if isinstance(u, str)])
    seen: set[str] = set()
    out: List[str] = []
    for u in urls:
        if not isinstance(u, str):
            continue
        s = u.strip()
        if not s.startswith("http"):
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _extract_urls_from_mixed_image_list(arr: List[Any]) -> List[str]:
    out: List[str] = []
    for x in arr:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
            continue
        if not isinstance(x, dict):
            continue
        u = (
            x.get("url")
            or x.get("image")
            or x.get("image_url")
            or x.get("pic_url")
            or x.get("picUrl")
            or x.get("big_url")
            or x.get("bigUrl")
            or x.get("thumb_url")
            or x.get("thumbUrl")
            or x.get("cover_url")
            or x.get("coverUrl")
        )
        if isinstance(u, str) and u.strip().startswith("http"):
            out.append(u.strip())
    return out


def normalize_images_field_in_data(data: dict) -> None:
    """Мутирует data['images'] (list или JSON-строка списка)."""
    if not isinstance(data, dict):
        return
    raw_im = data.get("images")
    encar = catalog_data_is_encar(data)

    if isinstance(raw_im, str):
        try:
            arr = json.loads(raw_im)
        except Exception:
            return
        if not isinstance(arr, list):
            return
        urls = _extract_urls_from_mixed_image_list(arr)
        ordered = order_image_urls_for_catalog(urls, encar=encar)
        data["images"] = json.dumps(ordered, ensure_ascii=False)
        return

    if isinstance(raw_im, list):
        urls = _extract_urls_from_mixed_image_list(raw_im)
        ordered = order_image_urls_for_catalog(urls, encar=encar)
        data["images"] = ordered
