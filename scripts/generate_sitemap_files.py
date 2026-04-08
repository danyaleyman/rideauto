#!/usr/bin/env python3
"""
Генерация XML sitemap на диск для cron (каталог в PostgreSQL).

  python scripts/generate_sitemap_files.py --dsn "$DATABASE_URL" --out /var/www/sitemap \\
    --base-url https://rideauto.ru --web-path /sitemap-gen/

Требуется: pip install psycopg2-binary
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape_text

try:
    import psycopg2
except ImportError:
    print("Install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent


def _sitemap_catalog_xml_body(base: str, car_ids: list[str]) -> str:
    from urllib.parse import quote

    base = base.rstrip("/")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for cid in car_ids:
        loc = f"{base}/car/{quote(cid, safe='')}"
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape_text(loc)}</loc>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("    <priority>0.7</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _count_rows(dsn: str) -> int:
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM cars")
            r = cur.fetchone()
            return int(r[0]) if r and r[0] is not None else 0


def _ids_slice(dsn: str, offset: int, limit: int) -> list[str]:
    if limit <= 0:
        return []
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT car_id FROM cars ORDER BY id DESC LIMIT %s OFFSET %s",
                (limit, max(0, offset)),
            )
            return [str(r[0]).strip() for r in cur.fetchall() if r and r[0]]


def main() -> None:
    p = argparse.ArgumentParser(description="Sitemap shards из PostgreSQL cars")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL", "").strip(), help="PostgreSQL DSN")
    p.add_argument("--out", required=True, help="Каталог вывода")
    p.add_argument(
        "--base-url",
        default=os.environ.get("PUBLIC_SITE_URL", "https://rideauto.ru").strip().rstrip("/"),
        help="Канонический origin сайта",
    )
    p.add_argument(
        "--web-path",
        default="/sitemap-gen/",
        help="Публичный префикс URL для шардов",
    )
    p.add_argument(
        "--shard",
        type=int,
        default=int((os.environ.get("WRA_SITEMAP_MAX_URLS") or "12000").strip() or "12000"),
        help="URL на шард (макс. 45000)",
    )
    args = p.parse_args()
    dsn = (args.dsn or "").strip()
    if not dsn:
        p.error("--dsn or DATABASE_URL required")
    cap = min(45000, max(1, args.shard))
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    base = args.base_url.rstrip("/")
    web_prefix = args.web_path.strip()
    if not web_prefix.startswith("/"):
        web_prefix = "/" + web_prefix
    if not web_prefix.endswith("/"):
        web_prefix += "/"

    total = _count_rows(dsn)
    n_parts = max(1, (total + cap - 1) // cap) if total > 0 else 1

    for part in range(1, n_parts + 1):
        offset = (part - 1) * cap
        ids = _ids_slice(dsn, offset, cap)
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
