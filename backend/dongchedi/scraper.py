"""
Асинхронный скрейпер 懂车帝: POST motor/pc/sh/sh_sku_list + опционально HTML карточки для цены (source_sh_price).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
import yaml

from dongchedi.brand_shards import DEFAULT_BRAND_SHARD_IDS
from dongchedi.browser_fetch import fetch_usedcar_html_playwright
from dongchedi.client import DEFAULT_HEADERS, fetch_params_car_html, fetch_usedcar_html, post_sku_list
from dongchedi.normalize import dongchedi_spec_car_id, row_matches_filters, sku_row_to_payload
from dongchedi.parse_detail import parse_params_raw_data_from_html, parse_sku_detail_from_html

log = logging.getLogger("dongchedi.scraper")


@dataclass
class ScrapeConfig:
    """Конфиг скрейпера: brand_ids / shard_brands расширяют охват листинга; enrich_detail даёт цену и галерею с карточки."""

    db_path: str = "encar_china.db"
    postgres_dsn: str = ""
    brand_id: Optional[str] = None
    brand_ids: Optional[List[str]] = None
    shard_brands: bool = False
    series_id: Optional[int] = None
    sh_city_name: Optional[str] = None
    age_range: Optional[str] = None
    year: Optional[int] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    limit: int = 0
    max_pages: int = 500
    page_size: int = 60
    concurrency: int = 8
    detail_concurrency: int = 6
    enrich_detail: bool = True
    cny_to_rub: float = 13.0
    request_timeout_s: float = 45.0
    delay_between_pages_s: float = 0.15
    cookie: Optional[str] = None
    start_shard: int = 1
    start_brand_id: Optional[str] = None
    # Писать checkpoint рядом с БД (shard_1based + page) для --resume.
    persist_checkpoint: bool = True
    resume: bool = False
    checkpoint_path: Optional[str] = None
    # Optional anti-bot fallback: render card page in headless browser.
    browser_fallback: bool = False
    browser_timeout_s: float = 25.0
    browser_concurrency: int = 2
    proxy_urls: Optional[List[str]] = None


def _clamp_limit(v: int) -> int:
    if v <= 0:
        return 0
    return min(v, 100)


def _year_bounds(cfg: ScrapeConfig) -> Tuple[Optional[int], Optional[int]]:
    if cfg.year is not None:
        return cfg.year, cfg.year
    return cfg.year_min, cfg.year_max


def _fen_to_cny_local(fen: Any) -> Optional[float]:
    try:
        v = int(fen)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return v / 100.0


def load_config_file(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def config_from_mapping(raw: Dict[str, Any], defaults: Optional[ScrapeConfig] = None) -> ScrapeConfig:
    base = defaults or ScrapeConfig()
    m = {k.replace("-", "_"): v for k, v in raw.items()}
    storage = m.pop("storage", None)
    if isinstance(storage, dict):
        pg = storage.get("postgres")
        if isinstance(pg, dict):
            d_sn = str(pg.get("dsn") or "").strip()
            if d_sn:
                base.postgres_dsn = d_sn
    raw_brand_ids = m.pop("brand_ids", None)
    if isinstance(raw_brand_ids, list):
        base.brand_ids = [str(x).strip() for x in raw_brand_ids if str(x).strip()]
    raw_proxy_urls = m.pop("proxy_urls", None)
    if isinstance(raw_proxy_urls, list):
        base.proxy_urls = [str(x).strip() for x in raw_proxy_urls if str(x).strip()]
    if m.pop("no_checkpoint", False):
        base.persist_checkpoint = False
    known = {f.name for f in fields(ScrapeConfig)}
    for k, v in m.items():
        if k in known and v is not None:
            setattr(base, k, v)
    if base.cookie is None:
        env_c = (os.environ.get("DONGCHEDI_COOKIE") or "").strip()
        if env_c:
            base.cookie = env_c
    if not (base.postgres_dsn or "").strip():
        base.postgres_dsn = (os.environ.get("DATABASE_URL") or "").strip()
    return base


def _brand_filters_base(cfg: ScrapeConfig) -> List[Optional[str]]:
    if cfg.brand_ids:
        return [str(x).strip() for x in cfg.brand_ids if str(x).strip()]
    if cfg.shard_brands:
        return [str(x).strip() for x in DEFAULT_BRAND_SHARD_IDS if str(x).strip()]
    if cfg.brand_id and str(cfg.brand_id).strip():
        return [str(cfg.brand_id).strip()]
    return [None]


def _apply_start_brand_id(filters: List[Optional[str]], cfg: ScrapeConfig) -> List[Optional[str]]:
    if not cfg.start_brand_id or not str(cfg.start_brand_id).strip():
        return filters
    target = str(cfg.start_brand_id).strip()
    if target in filters:
        return filters[filters.index(target) :]
    log.warning("start_brand_id=%s not found in shard set, ignoring", target)
    return filters


def _brand_filters_for_listing(cfg: ScrapeConfig) -> List[Optional[str]]:
    """Полный список проходов листинга (до среза по --start-shard / --resume)."""
    return _apply_start_brand_id(_brand_filters_base(cfg), cfg)


def _default_checkpoint_path(db_path: str) -> str:
    p = Path(db_path).resolve()
    return str(p.with_name(p.stem + ".scraper.checkpoint.json"))


def _checkpoint_load(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _checkpoint_save(path: str, shard_1based: int, page: int) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"shard_1based": int(shard_1based), "page": int(page), "saved_at": time.time()},
                f,
                ensure_ascii=False,
                indent=2,
            )
        os.replace(tmp, path)
    except OSError as e:
        log.warning("checkpoint write failed: %s", e)


def _checkpoint_clear(path_v: Optional[str]) -> None:
    if not path_v:
        return
    try:
        os.unlink(path_v)
    except OSError:
        pass


def _headers_with_cookie(cookie: Optional[str]) -> Dict[str, str]:
    h = dict(DEFAULT_HEADERS)
    if cookie:
        h["Cookie"] = cookie
    return h


def _resolved_postgres_dsn(cfg: ScrapeConfig) -> str:
    dsn = (cfg.postgres_dsn or "").strip()
    if dsn:
        return dsn
    return (os.environ.get("DATABASE_URL") or "").strip()


async def run_scrape(cfg: ScrapeConfig) -> int:
    year_min, year_max = _year_bounds(cfg)
    lim = _clamp_limit(cfg.limit)
    page_sz = max(1, min(100, int(cfg.page_size)))

    need_price = cfg.price_min is not None or cfg.price_max is not None
    enrich = cfg.enrich_detail or need_price
    if need_price and not enrich:
        enrich = True
        log.warning("price_min/max требуют карточку — включаем enrich_detail")

    db_path = str(Path(cfg.db_path).resolve())

    def sync_upsert_batch(batch: List[Tuple[str, str]]) -> int:
        if not batch:
            return 0
        dsn = _resolved_postgres_dsn(cfg)
        if not dsn:
            log.error("Dongchedi: нужен storage.postgres.dsn или DATABASE_URL")
            return 0
        from catalog_pg_upsert import upsert_json_batch

        return upsert_json_batch(dsn, batch, batch_commit=max(10, len(batch)))

    list_sem = asyncio.Semaphore(max(1, cfg.concurrency))
    detail_sem = asyncio.Semaphore(max(1, cfg.detail_concurrency))
    browser_sem = asyncio.Semaphore(max(1, cfg.browser_concurrency))
    headers = _headers_with_cookie(cfg.cookie)
    timeout = aiohttp.ClientTimeout(total=cfg.request_timeout_s + 35)
    connector = aiohttp.TCPConnector(limit=max(12, cfg.concurrency + cfg.detail_concurrency))
    proxy_pool = [str(p).strip() for p in (cfg.proxy_urls or []) if str(p).strip()]

    def pick_proxy() -> Optional[str]:
        if not proxy_pool:
            return None
        return random.choice(proxy_pool)

    saved = 0
    seen: Set[str] = set()
    stop = False

    filters_full = _brand_filters_for_listing(cfg)
    total_shards = len(filters_full)

    cp_path: Optional[str] = None
    if cfg.persist_checkpoint:
        cp_path = cfg.checkpoint_path or _default_checkpoint_path(db_path)

    resume_shard_1 = 1
    resume_page = 1
    if cfg.resume and cp_path:
        cpd = _checkpoint_load(cp_path)
        if cpd:
            resume_shard_1 = max(1, int(cpd.get("shard_1based", 1)))
            resume_page = max(1, int(cpd.get("page", 1)))
            log.info("resume: shard %s/%s page=%s (%s)", resume_shard_1, total_shards, resume_page, cp_path)
        else:
            log.warning("resume: файла checkpoint нет (%s)", cp_path)
            if cfg.start_shard and int(cfg.start_shard) > 1:
                resume_shard_1 = int(cfg.start_shard)
                log.info("используем --start-shard=%s", resume_shard_1)
    elif cfg.start_shard and int(cfg.start_shard) > 1:
        resume_shard_1 = int(cfg.start_shard)

    slice_start = resume_shard_1 - 1
    if slice_start < len(filters_full):
        brand_filters = filters_full[slice_start:]
    else:
        log.warning(
            "resume/start_shard=%s вне диапазона (%s марок всего), нечего качать",
            resume_shard_1,
            total_shards,
        )
        brand_filters = []

    if brand_filters and (len(brand_filters) > 1 or brand_filters[0] is not None):
        log.info(
            "sh_sku_list: в этом прогоне %s проход(ов) (всего в индексе %s, shard_brands=%s)",
            len(brand_filters),
            total_shards,
            cfg.shard_brands,
        )
    async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=connector) as session:

        async def detail_for(sku: str) -> Optional[Dict[str, Any]]:
            """Несколько попыток: антибот/обрыв отдачи часто дают HTML без skuDetail."""
            sd: Optional[Dict[str, Any]] = None
            for attempt in range(3):
                async with detail_sem:
                    st, html = await fetch_usedcar_html(
                        session, sku, timeout_s=cfg.request_timeout_s, proxy=pick_proxy()
                    )
                if st == 200 and html:
                    sd = parse_sku_detail_from_html(html)
                    if sd:
                        break
                if attempt < 2:
                    await asyncio.sleep(0.4 * float(attempt + 1))
            if not sd:
                if cfg.browser_fallback:
                    async with browser_sem:
                        st3, html3 = await fetch_usedcar_html_playwright(
                            sku,
                            timeout_s=cfg.browser_timeout_s,
                        )
                    if st3 == 200 and html3:
                        sd = parse_sku_detail_from_html(html3)
                if not sd:
                    return None
            cid = dongchedi_spec_car_id(sd)
            if cid:
                raw: Optional[Dict[str, Any]] = None
                for attempt in range(2):
                    async with detail_sem:
                        st2, phtml = await fetch_params_car_html(
                            session,
                            cid,
                            referer_sku_id=sku,
                            timeout_s=cfg.request_timeout_s,
                            proxy=pick_proxy(),
                        )
                    if st2 == 200 and phtml:
                        raw = parse_params_raw_data_from_html(phtml)
                        if raw:
                            break
                    if attempt < 1:
                        await asyncio.sleep(0.35)
                if raw:
                    sd = dict(sd)
                    sd["_params_raw"] = raw
            return sd

        first_shard_in_run = True
        for shard_i, brand_for_list in enumerate(brand_filters):
            global_shard_1based = slice_start + shard_i + 1
            if len(brand_filters) > 1 or brand_for_list:
                log.info(
                    "listing shard %s/%s brand=%s",
                    global_shard_1based,
                    total_shards,
                    brand_for_list or "—",
                )
            page = resume_page if first_shard_in_run else 1
            first_shard_in_run = False
            while page <= cfg.max_pages and not stop:
                if cp_path and cfg.persist_checkpoint:
                    await asyncio.to_thread(_checkpoint_save, cp_path, global_shard_1based, page)
                status, payload = 0, None
                for list_try in range(3):
                    async with list_sem:
                        status, payload = await post_sku_list(
                            session,
                            page=page,
                            limit=page_sz,
                            brand_id=brand_for_list,
                            sh_city_name=cfg.sh_city_name,
                            age_range=cfg.age_range,
                            timeout_s=cfg.request_timeout_s,
                            proxy=pick_proxy(),
                        )
                    if status == 200 and payload:
                        break
                    if list_try < 2:
                        log.warning(
                            "list retry %s/3 page %s brand=%s http=%s (empty or non-json body)",
                            list_try + 1,
                            page,
                            brand_for_list,
                            status,
                        )
                        await asyncio.sleep(0.45 * (list_try + 1))

                if status != 200 or not payload:
                    log.warning(
                        "list page %s brand=%s http=%s api_status=%s",
                        page,
                        brand_for_list,
                        status,
                        None,
                    )
                    break

                raw_st = payload.get("status")
                if raw_st is None:
                    # Иногда Dongchedi отдает полезный payload без status (или с code/msg в другом формате).
                    # В таком случае ориентируемся на наличие data/search_sh_sku_info_list ниже.
                    alt_st = payload.get("code")
                    if alt_st is not None:
                        raw_st = alt_st
                if raw_st is not None:
                    try:
                        api_st = int(raw_st)
                    except (TypeError, ValueError):
                        api_st = -1
                    if api_st != 0:
                        log.warning(
                            "list page %s brand=%s http=%s api_status=%s",
                            page,
                            brand_for_list,
                            status,
                            raw_st,
                        )
                        break

                data = payload.get("data") or {}
                rows = data.get("search_sh_sku_info_list") or []
                if not isinstance(rows, list) or not rows:
                    log.info("empty list page %s brand=%s, next shard", page, brand_for_list)
                    break

                candidates: List[Dict[str, Any]] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    sku = row.get("sku_id")
                    if sku is None:
                        continue
                    sid = str(sku).strip()
                    if not sid or sid in seen:
                        continue
                    if not row_matches_filters(
                        row,
                        series_id=cfg.series_id,
                        year_min=year_min,
                        year_max=year_max,
                    ):
                        continue
                    candidates.append(row)

                details: Dict[str, Optional[Dict[str, Any]]] = {}
                if enrich and candidates:
                    detail_tasks = [detail_for(str(r.get("sku_id"))) for r in candidates]
                    resolved = await asyncio.gather(*detail_tasks)
                    for r, d in zip(candidates, resolved):
                        details[str(r.get("sku_id"))] = d

                batch: List[Tuple[str, str]] = []
                for row in candidates:
                    sid = str(row.get("sku_id")).strip()
                    det = details.get(sid) if enrich else None
                    price_cny: Optional[float] = None
                    if det:
                        price_cny = _fen_to_cny_local(det.get("source_sh_price"))

                    if not row_matches_filters(
                        row,
                        series_id=cfg.series_id,
                        year_min=year_min,
                        year_max=year_max,
                        price_min_cny=cfg.price_min,
                        price_max_cny=cfg.price_max,
                        price_cny=price_cny if enrich else None,
                    ):
                        continue

                    if need_price and enrich and (price_cny is None or price_cny <= 0):
                        continue

                    seen.add(sid)
                    payload_doc = sku_row_to_payload(row, detail=det, cny_to_rub=cfg.cny_to_rub)
                    inner = (payload_doc.get("data") or {})
                    if not inner:
                        continue
                    car_id = f"dongchedi-{sid}"
                    batch.append((car_id, json.dumps(payload_doc, ensure_ascii=False)))

                    if lim and len(seen) >= lim:
                        stop = True
                        break

                if batch:
                    n = await asyncio.to_thread(sync_upsert_batch, batch)
                    saved += n
                    log.info(
                        "page %s brand=%s: +%s rows (total saved %s)",
                        page,
                        brand_for_list,
                        n,
                        saved,
                    )

                if stop:
                    break

                if not data.get("has_more"):
                    log.info("has_more=false at page %s brand=%s", page, brand_for_list)
                    break

                page += 1
                if cfg.delay_between_pages_s > 0:
                    await asyncio.sleep(cfg.delay_between_pages_s)

            if stop:
                break

    if not stop and cp_path and cfg.persist_checkpoint:
        _checkpoint_clear(cp_path)
        log.info("checkpoint удалён: прогон завершён до конца")

    return saved


def setup_logging(level: str = "INFO") -> None:
    lv = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=lv, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def main(argv: Optional[List[str]] = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="懂车帝 async scraper → PostgreSQL")
    p.add_argument("--config", type=str, default=None)
    p.add_argument("--db", type=str, default=None)
    p.add_argument("--brand-id", type=str, default=None, help="Числовой brand_id (напр. 4 = 宝马)")
    p.add_argument(
        "--shard-brands",
        action="store_true",
        help="Много проходов sh_sku_list по маркам (обход лимита ~10k без brand)",
    )
    p.add_argument("--series-id", type=int, default=None)
    p.add_argument("--start-shard", type=int, default=None, help="Продолжить c N-го shard (1-based), если нет --resume")
    p.add_argument("--start-brand-id", type=str, default=None, help="Продолжить c указанного brand_id")
    p.add_argument(
        "--resume",
        action="store_true",
        help="Читать shard/page из checkpoint (файл по умолчанию рядом с БД: *.scraper.checkpoint.json)",
    )
    p.add_argument("--no-checkpoint", action="store_true", help="Не записывать checkpoint (и не использовать при --resume)")
    p.add_argument("--checkpoint", type=str, default=None, help="Путь к JSON checkpoint")
    p.add_argument("--city", type=str, default=None, help="sh_city_name, напр. 北京")
    p.add_argument("--age-range", type=str, default=None, help="Напр. 3,5 как в HAR")
    p.add_argument("--year", type=int, default=None)
    p.add_argument("--year-min", type=int, default=None)
    p.add_argument("--year-max", type=int, default=None)
    p.add_argument("--price-min", type=float, default=None)
    p.add_argument("--price-max", type=float, default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--page-size", type=int, default=None, help="1–100 на запрос")
    p.add_argument("--concurrency", type=int, default=None)
    p.add_argument("--detail-concurrency", type=int, default=None)
    p.add_argument("--no-enrich-detail", action="store_true", help="Без запроса карточек (без my_price)")
    p.add_argument(
        "--browser-fallback",
        action="store_true",
        help="Fallback через Playwright, если карточка отдает пустой HTML",
    )
    p.add_argument("--browser-timeout", type=float, default=None, help="Timeout браузерного fallback (сек)")
    p.add_argument("--browser-concurrency", type=int, default=None, help="Параллелизм браузерного fallback")
    p.add_argument(
        "--proxy-url",
        action="append",
        default=None,
        help="HTTP proxy URL, можно несколько раз: http://user:pass@host:port",
    )
    p.add_argument("--cny-to-rub", type=float, default=None)
    p.add_argument("--log-level", type=str, default="INFO")
    args = p.parse_args(argv)

    cfg = ScrapeConfig()
    if args.config:
        cfg = config_from_mapping(load_config_file(args.config), cfg)
    if args.db is not None:
        cfg.db_path = args.db
    if args.shard_brands:
        cfg.shard_brands = True
    if args.brand_id is not None:
        cfg.brand_id = args.brand_id or None
    if args.series_id is not None:
        cfg.series_id = args.series_id
    if args.start_shard is not None:
        cfg.start_shard = max(1, int(args.start_shard))
    if args.start_brand_id is not None:
        cfg.start_brand_id = (args.start_brand_id or "").strip() or None
    if args.resume:
        cfg.resume = True
    if args.no_checkpoint:
        cfg.persist_checkpoint = False
    if args.checkpoint is not None:
        cfg.checkpoint_path = (args.checkpoint or "").strip() or None
    if args.city is not None:
        cfg.sh_city_name = args.city or None
    if args.age_range is not None:
        cfg.age_range = args.age_range or None
    if args.year is not None:
        cfg.year = args.year
    if args.year_min is not None:
        cfg.year_min = args.year_min
    if args.year_max is not None:
        cfg.year_max = args.year_max
    if args.price_min is not None:
        cfg.price_min = args.price_min
    if args.price_max is not None:
        cfg.price_max = args.price_max
    if args.limit is not None:
        cfg.limit = args.limit
    if args.max_pages is not None:
        cfg.max_pages = args.max_pages
    if args.page_size is not None:
        cfg.page_size = max(1, min(100, args.page_size))
    if args.concurrency is not None:
        cfg.concurrency = args.concurrency
    if args.detail_concurrency is not None:
        cfg.detail_concurrency = args.detail_concurrency
    if args.no_enrich_detail:
        cfg.enrich_detail = False
    if args.browser_fallback:
        cfg.browser_fallback = True
    if args.browser_timeout is not None:
        cfg.browser_timeout_s = float(args.browser_timeout)
    if args.browser_concurrency is not None:
        cfg.browser_concurrency = max(1, int(args.browser_concurrency))
    if args.proxy_url:
        cfg.proxy_urls = [str(x).strip() for x in args.proxy_url if str(x).strip()]
    if args.cny_to_rub is not None:
        cfg.cny_to_rub = args.cny_to_rub

    setup_logging(args.log_level)
    t0 = time.perf_counter()
    n = asyncio.run(run_scrape(cfg))
    log.info("done: saved=%s in %.2fs", n, time.perf_counter() - t0)


if __name__ == "__main__":
    main()
