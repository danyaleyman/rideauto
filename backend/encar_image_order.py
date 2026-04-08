"""
Порядок URL фото Encar по номеру кадра (_001.jpg …) — без зависимостей вроде aiohttp.

Нужен для catalog_export_utils / postgres_catalog_sync и FastAPI (slim каталог).
"""
from __future__ import annotations

import re
from typing import List

_ENC_IMG_SEQ = re.compile(r"_(\d+)\.(?:jpe?g|png|webp)(?:\?|$)", re.I)


def _encar_image_url_seq(url: str) -> int:
    if not url or not isinstance(url, str):
        return 10**9
    m = _ENC_IMG_SEQ.search(url)
    if not m:
        return 10**9
    try:
        return int(m.group(1), 10)
    except ValueError:
        return 10**9


def _sort_encar_image_url_list(urls: List[str]) -> List[str]:
    return sorted((u for u in urls if isinstance(u, str)), key=lambda u: (_encar_image_url_seq(u), u))


def _sort_h_images_list_entries(items: List[dict]) -> List[dict]:
    def seq(h: dict) -> int:
        path = str((h or {}).get("path") or "")
        m = _ENC_IMG_SEQ.search(path)
        if m:
            try:
                return int(m.group(1), 10)
            except ValueError:
                pass
        c = (h or {}).get("code")
        if isinstance(c, int):
            return int(c)
        if isinstance(c, str) and c.strip().isdigit():
            return int(c.strip(), 10)
        return 10**9

    return sorted((x for x in items if isinstance(x, dict)), key=lambda h: (seq(h), str(h.get("path") or "")))
