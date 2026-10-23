"""Доразведка каталога Encar мелкими срезами (repair-режим).

Зачем: глубокий ``offset`` в list API Encar упирается в «окно» выдачи (~19 тыс.
результатов на запрос) и дальше отдаёт повторяющуюся страницу. Обход бренда
целиком поэтому теряет 30-55 % объявлений.

Замер 2026-10-20 (prod, /tmp/encar_vs_db.txt):

    기아   в БД 22 011 / Encar 48 398   (окно: offset 18 500 отдаёт данные, 19 000 — уже повтор)
    현대   в БД 21 855 / Encar 48 328
    BMW    в БД 11 137 / Encar 17 327
    벤츠    в БД 10 953 / Encar 16 796

Срез с ``Count`` много меньше окна (``_.Manufacturer.X._.Model.<модель>.``)
обходится детерминированно: offset идёт 0..Count без stall-прыжков из
``workers._list_one_variant`` (там 50 полных страниц без новых id дают скачок
+20 000 — на ремонтном проходе, где старые id уже в базе, это гарантированно
перепрыгнуло бы недостающее).

Скрипт только наполняет ``scraper_pending_ids``; карточки потом тянет
``encar_scraper.py --only-pending``.

Примеры:
    # срезы из файла: по строке "car_type<TAB>q_suffix"
    python backend/encar_deep_discover.py --config scraper_config.yaml \
        --slices-file /tmp/encar_slices.tsv

    # срезы по моделям из нашей БД для брендов, где Encar.Count > cars (+--min-gap)
    python backend/encar_deep_discover.py --config scraper_config.yaml \
        --from-db --min-gap 100

    # только посчитать срезы, ничего не писать
    python backend/encar_deep_discover.py --config scraper_config.yaml --from-db --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from encar_scraper import _postgres_dsn_for_checkpoint, load_config, setup_logging
from scraper_pipeline.checkpoint_pg import CheckpointAsync
from scraper_pipeline.encar.client import AsyncEncarClient

Slices = List[Tuple[str, str]]  # (car_type, q_suffix)


def _read_slices_file(path: str) -> Slices:
    out: Slices = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            car_type, suffix = line.split("\t", 1)
        elif "|" in line:
            car_type, suffix = line.split("|", 1)
        else:
            car_type, suffix = "kor", line
        car_type, suffix = car_type.strip(), suffix.strip()
        if car_type not in ("kor", "for"):
            raise ValueError(f"неизвестный car_type={car_type!r} в {path}")
        if not suffix.startswith("_."):
            raise ValueError(f"q_suffix должен начинаться с '_._': {suffix!r}")
        out.append((car_type, suffix))
    return out


def _db_brand_models(dsn: str, brands: Optional[List[str]] = None) -> Dict[str, List[Tuple[str, int]]]:
    import psycopg2

    sql = (
        "select mark, model, count(*) from cars where source='encar' "
        + ("and mark = any(%s) " if brands else "")
        + "group by 1, 2 order by 1, 3 desc"
    )
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql, (brands,) if brands else None)
        out: Dict[str, List[Tuple[str, int]]] = {}
        for mark, model, n in cur.fetchall():
            if not mark or not str(mark).strip():
                continue
            if not model or not str(model).strip():
                continue
            out.setdefault(str(mark), []).append((str(model), int(n)))
    return out


def _db_brand_counts(dsn: str) -> Dict[str, int]:
    import psycopg2

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select mark, count(*) from cars where source='encar' group by 1")
        return {str(m): int(n) for m, n in cur.fetchall() if m}


def _load_state(path: str) -> Dict[str, int]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        return {str(k): int(v) for k, v in json.loads(p.read_text(encoding="utf-8")).items()}
    except Exception:  # noqa: BLE001
        return {}


def _save_state(path: str, state: Dict[str, int]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def _slice_key(car_type: str, suffix: str) -> str:
    return f"{car_type}\t{suffix}"


def _cars_present_fn(dsn: str) -> Callable[[List[str]], set]:
    """Фабрика проверки «id уже есть в cars» — для бэкфилла в отдельном scope.

    ``checkpoint.is_collected`` смотрит ``scraper_collected_ids`` своего scope, поэтому
    при scope='encar_backfill' он ничего не знает о 118k уже собранных машин и вернул бы
    их в очередь повторно. Здесь проверяем напрямую по таблице cars (один запрос на страницу).
    """

    import psycopg2

    def _check(ids: List[str]) -> set:
        if not ids:
            return set()
        with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("select car_id from cars where car_id = any(%s)", (ids,))
            return {str(r[0]) for r in cur.fetchall()}

    return _check


async def _list_count(client: AsyncEncarClient, car_type: str, suffix: str, log) -> int:
    data, status, err = await client.fetch_list_page(0, 1, car_type, q_suffix=suffix)
    if status != 200 or not data:
        log.warning("Срез не посчитан: type=%s suffix=%s status=%s err=%s", car_type, suffix, status, err)
        return -1
    return int(data.get("Count") or data.get("TotalCount") or data.get("totalCount") or 0)


async def _walk_slice(
    client: AsyncEncarClient,
    checkpoint: CheckpointAsync,
    car_type: str,
    suffix: str,
    page_size: int,
    delay_min: float,
    delay_max: float,
    state: Dict[str, int],
    state_path: str,
    max_pages: int,
    log,
    in_cars: Optional[Callable[[List[str]], set]] = None,
) -> Tuple[int, int]:
    """Обходит один срез от offset до Count. Возвращает (id просмотрено, добавлено в pending)."""
    key = _slice_key(car_type, suffix)
    count = await _list_count(client, car_type, suffix, log)
    if count <= 0:
        return 0, 0
    offset = int(state.get(key, 0))
    if offset >= count:
        log.info("Срез уже пройден: type=%s suffix=%s count=%s", car_type, suffix, count)
        return count, 0
    seen_ids = 0
    added_total = 0
    pages = 0
    fail_streak = 0
    while offset < count:
        if max_pages > 0 and pages >= max_pages:
            log.info(
                "Срез остановлен по --max-pages (%s): type=%s suffix=%s offset=%s/%s",
                max_pages, car_type, suffix, offset, count,
            )
            break
        data, status, err = await client.fetch_list_page(offset, page_size, car_type, q_suffix=suffix)
        if status != 200 or not data:
            fail_streak += 1
            log.warning(
                "Срез: страница не получена type=%s suffix=%s offset=%s status=%s err=%s (серия %s)",
                car_type, suffix, offset, status, err, fail_streak,
            )
            if fail_streak >= 5:
                log.error("Срез прерван (5 подряд ошибок): type=%s suffix=%s offset=%s",
                          car_type, suffix, offset)
                break
            await asyncio.sleep(min(120.0, 10.0 * fail_streak))
            continue
        fail_streak = 0
        items = data.get("SearchResults") or []
        if not items:
            log.info("Срез исчерпан: type=%s suffix=%s offset=%s count=%s", car_type, suffix, offset, count)
            break
        to_add: List[Tuple[str, str, Optional[dict]]] = []
        page_ids: List[str] = []
        by_id: Dict[str, dict] = {}
        for item in items:
            car_id = str(item.get("Id") or "")
            if not car_id or car_id in by_id:
                continue
            by_id[car_id] = item
            page_ids.append(car_id)
        if in_cars is not None:
            known = await asyncio.to_thread(in_cars, page_ids)
        else:
            known = {cid for cid in page_ids if await checkpoint.is_collected(cid)}
        for car_id in page_ids:
            if car_id in known:
                continue
            to_add.append((car_id, car_type, by_id[car_id]))
        added = await checkpoint.add_pending_batch(to_add) if to_add else 0
        seen_ids += len(items)
        added_total += added
        pages += 1
        offset += page_size
        state[key] = min(offset, count)
        if pages % 10 == 0:
            _save_state(state_path, state)
        if pages % 20 == 0:
            log.info(
                "Срез прогресс: type=%s suffix=%s offset=%s/%s (+%s новых, всего %s)",
                car_type, suffix, offset, count, added, added_total,
            )
        await asyncio.sleep(random.uniform(delay_min, delay_max))
    _save_state(state_path, state)
    log.info(
        "Срез готов: type=%s suffix=%s count=%s страниц=%s новых=%s",
        car_type, suffix, count, pages, added_total,
    )
    return seen_ids, added_total


def _pending_count(dsn: str, scope: str) -> int:
    import psycopg2

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("select count(*) from scraper_pending_ids where scope = %s", (scope,))
        row = cur.fetchone()
    return int(row[0]) if row else 0


async def _build_slices_from_db(
    config: dict,
    dsn: str,
    brands: Optional[List[str]],
    min_gap: int,
    delay_min: float,
    delay_max: float,
    log,
) -> Slices:
    db_models = _db_brand_models(dsn, brands)
    db_counts = _db_brand_counts(dsn)
    slices: Slices = []
    async with AsyncEncarClient(config, log) as client:
        for mark in sorted(db_models, key=lambda m: -db_counts.get(m, 0)):
            n_kor = await _list_count(client, "kor", f"_.Manufacturer.{mark}.", log)
            n_for = await _list_count(client, "for", f"_.Manufacturer.{mark}.", log)
            car_type, total = ("kor", n_kor) if n_kor >= n_for else ("for", n_for)
            if total <= 0:
                log.warning("Бренд пропущен (Count=0 в обоих разделах): %s", mark)
                continue
            gap = total - db_counts.get(mark, 0)
            log.info(
                "Бренд %s: Encar(%s)=%s, в БД=%s, разрыв=%s, моделей=%s",
                mark, car_type, total, db_counts.get(mark, 0), gap, len(db_models[mark]),
            )
            if gap < min_gap:
                continue
            for model, _db_n in db_models[mark]:
                slices.append((car_type, f"_.Manufacturer.{mark}._.Model.{model}."))
            await asyncio.sleep(random.uniform(delay_min, delay_max))
    return slices


async def run(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    log = setup_logging(config)
    http_cfg = config.get("http", {}) or {}
    page_size = int(http_cfg.get("list_page_size", 100) or 100)
    delay_min = float(http_cfg.get("list_page_delay_min", 0.2) or 0.2)
    delay_max = max(delay_min, float(http_cfg.get("list_page_delay_max", 0.6) or 0.6))
    dsn = _postgres_dsn_for_checkpoint(config)
    if not dsn:
        raise ValueError("Нужен DSN Postgres (storage.postgres.dsn / DATABASE_URL)")

    brands = [b.strip() for b in (args.brands or "").split(",") if b.strip()] or None
    if args.slices_file:
        slices = _read_slices_file(args.slices_file)
    else:
        slices = await _build_slices_from_db(config, dsn, brands, args.min_gap, delay_min, delay_max, log)

    log.info("Срезов к обходу: %s (parallel=%s, page_size=%s)", len(slices), args.parallel, page_size)
    if args.dry_run:
        for car_type, suffix in slices:
            log.info("  срез: %s %s", car_type, suffix)
        return
    if not slices:
        log.warning("Список срезов пуст — нечего делать")
        return

    checkpoint_cfg = config.get("checkpoint", {}) or {}
    scope = (args.scope or str(checkpoint_cfg.get("scope", "encar"))).strip() or "encar"
    in_cars = _cars_present_fn(dsn) if args.dedupe_by_cars else None
    log.info("Чекпоинт scope=%s, дедуп=%s", scope, "cars" if in_cars else "scraper_collected_ids")
    checkpoint = CheckpointAsync(
        dsn=dsn,
        scope=scope,
        max_pending=int(checkpoint_cfg.get("max_pending_ids", 500000)),
    )
    await checkpoint.connect()
    state = _load_state(args.state_file)
    started = time.time()
    totals = {"seen": 0, "added": 0}
    sem = asyncio.Semaphore(max(1, int(args.parallel)))
    lock = asyncio.Lock()

    try:
        async with AsyncEncarClient(config, log) as client:
            async def _one(car_type: str, suffix: str) -> None:
                async with sem:
                    try:
                        seen, added = await _walk_slice(
                            client, checkpoint, car_type, suffix,
                            page_size, delay_min, delay_max,
                            state, args.state_file, args.max_pages, log,
                            in_cars=in_cars,
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.exception("Срез упал: type=%s suffix=%s: %s", car_type, suffix, exc)
                        return
                    async with lock:
                        totals["seen"] += seen
                        totals["added"] += added

            await asyncio.gather(*[_one(ct, qs) for ct, qs in slices])
    finally:
        await checkpoint.close()
        _save_state(args.state_file, state)
        try:
            pend = _pending_count(dsn, scope)
        except Exception:  # noqa: BLE001
            pend = -1
        log.info(
            "Доразведка завершена: срезов=%s просмотрено id=%s новых в pending=%s, pending в БД=%s, elapsed=%.1fs",
            len(slices), totals["seen"], totals["added"], pend, time.time() - started,
        )


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description="Encar deep discover: обход мелких срезов без stall-прыжков")
    p.add_argument("--config", default=str(repo_root / "scraper_config.yaml"), help="Config YAML path")
    p.add_argument("--slices-file", default="", help='Файл срезов: "car_type<TAB>q_suffix" на строку')
    p.add_argument("--from-db", action="store_true", help="Собрать срезы по моделям из cars для брендов с разрывом")
    p.add_argument("--brands", default="", help="Ограничить бренды (через запятую)")
    p.add_argument("--min-gap", type=int, default=100, help="Минимальный разрыв Encar.Count - rows в БД")
    p.add_argument("--parallel", type=int, default=3, help="Одновременных срезов")
    p.add_argument("--max-pages", type=int, default=0, help="Предохранитель: страниц на срез (0 = без лимита)")
    p.add_argument("--state-file", default="/tmp/encar_deep_discover_state.json", help="JSON с прогрессом срезов")
    p.add_argument("--scope", default="", help="Scope чекпоинта (по умолчанию из конфига)")
    p.add_argument("--dedupe-by-cars", action="store_true",
                   help="Не добавлять id, уже присутствующие в cars (обязательно для отдельного scope)")
    p.add_argument("--dry-run", action="store_true", help="Только посчитать бренды/срезы, в pending не писать")
    args = p.parse_args()
    if not args.slices_file and not args.from_db:
        p.error("нужен --slices-file или --from-db")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
