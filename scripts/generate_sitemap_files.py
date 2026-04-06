#!/usr/bin/env python3
"""
Генерация XML sitemap на диск для cron (большие каталоги: не держать 500k URL в памяти API).

  python scripts/generate_sitemap_files.py --db encar_cars.db --out /var/www/sitemap \\
    --base-url https://rideauto.ru --web-path /sitemap-gen/

Затем в nginx: location /sitemap-gen/ { alias /var/www/sitemap/; }
robots.txt / основной индекс могут ссылаться на …/sitemap-gen/sitemap-index.xml
(скопируйте сгенерированный sitemap-index.xml или включите в деплой).

Требуется тот же Python-окружение, что и для backend (aiohttp не нужен).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api_server import (  # noqa: E402
    _sitemap_catalog_xml_body,
    _sitemap_collect_car_ids_slice,
    _sitemap_count_rows,
)
from xml.sax.saxutils import escape as xml_escape_text  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Записать шардированные sitemap-catalog-*.xml на диск")
    p.add_argument("--db", required=True, help="SQLite Корея (encar_cars.db)")
    p.add_argument("--db-china", default="", help="Китайский каталог (опционально)")
    p.add_argument("--out", required=True, help="Каталог вывода")
    p.add_argument(
        "--base-url",
        default=os.environ.get("PUBLIC_SITE_URL", "https://rideauto.ru").strip().rstrip("/"),
        help="Канонический origin сайта",
    )
    p.add_argument(
        "--web-path",
        default="/sitemap-gen/",
        help="Публичный префикс URL, под которым nginx отдаёт файлы из --out (со слэшем на конце)",
    )
    p.add_argument(
        "--shard",
        type=int,
        default=int((os.environ.get("WRA_SITEMAP_MAX_URLS") or "12000").strip() or "12000"),
        help="URL на шард (макс. 45000)",
    )
    args = p.parse_args()
    cap = min(45000, max(1, args.shard))
    china_arg = args.db_china.strip() or None
    db_k = str(Path(args.db).expanduser().resolve())
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    base = args.base_url.rstrip("/")
    web_prefix = args.web_path.strip()
    if not web_prefix.startswith("/"):
        web_prefix = "/" + web_prefix
    if not web_prefix.endswith("/"):
        web_prefix += "/"

    china_path = str(Path(china_arg).expanduser().resolve()) if china_arg else ""
    nk = _sitemap_count_rows(db_k)
    nc = _sitemap_count_rows(china_path) if china_path else 0
    total = nk + nc
    n_parts = max(1, (total + cap - 1) // cap) if total > 0 else 1

    for part in range(1, n_parts + 1):
        offset = (part - 1) * cap
        ids = _sitemap_collect_car_ids_slice(db_k, china_arg, offset, cap)
        (out / f"sitemap-catalog-{part}.xml").write_text(
            _sitemap_catalog_xml_body(base, ids), encoding="utf-8"
        )

    static_pages_loc = f"{base}/sitemap-pages.xml"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <sitemap><loc>{xml_escape_text(static_pages_loc)}</loc></sitemap>",
    ]
    for i in range(1, n_parts + 1):
        loc = f"{base}{web_prefix}sitemap-catalog-{i}.xml"
        lines.append(f"  <sitemap><loc>{xml_escape_text(loc)}</loc></sitemap>")
    lines.append("</sitemapindex>")
    (out / "sitemap-index.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {n_parts} шард(ов), sitemap-index.xml → {out}")


if __name__ == "__main__":
    main()
