"""
Read-only enrich из Postgres `term_translation_cache`: до `max_rounds` последовательных batched SELECT по UNNEST (пока не покрыты ключи).
Не обновляет hit_count и не пишет в БД — в отличие от PgTermLocalizer._read_cache().
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from fastapi_app.catalog_term_enrichment import canonical_catalog_enrich_domain, normalize_catalog_lookup_key
from fastapi_app.metrics.prometheus import inc_cache_lookup
from localization.term_localizer import detect_lang

_log = logging.getLogger(__name__)

_PG_DOMAINS_BY_ENRICH: Dict[str, Tuple[str, ...]] = {
    "mark": ("mark",),
    "model": ("model",),
    "generation": ("generation",),
    "configuration": ("configuration", "trim_name", "gradeName"),
    "gradeName": ("gradeName", "configuration", "trim_name"),
    "trim_name": ("trim_name", "configuration", "gradeName"),
    "modelGroupName": ("modelGroupName",),
    "engine_type": ("fuel_type", "engine_type"),
    "drive_type": ("drive_type", "prep_drive_type"),
    "prep_drive_type": ("prep_drive_type", "drive_type"),
    "body_type": ("body_type",),
    "color": ("color",),
    "transmission_type": ("transmission_type",),
}


@dataclass(frozen=True)
class CatalogEnrichPgOutcome:
    hits_ru: int
    hits_en: int
    keys_queried: int
    truncated: bool
    rounds_executed: int


def _text_variants(tin: str) -> Tuple[str, ...]:
    raw = (tin or "").strip()
    nk = normalize_catalog_lookup_key(raw)
    if not nk:
        return ()
    out: List[str] = []
    seen: Set[str] = set()
    for cand in (raw, nk):
        k = cand.strip()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return tuple(out)


def _needs_ru_en(row: Dict[str, Any]) -> Tuple[bool, bool]:
    return (not (row.get("ru") or "").strip(), not (row.get("en") or "").strip())


def _domains_for(row: Dict[str, Any]) -> Tuple[str, ...]:
    raw_dom = (row.get("domain") or "").strip()
    canon = canonical_catalog_enrich_domain(raw_dom)
    return _PG_DOMAINS_BY_ENRICH.get(canon, (canon,) if canon else tuple())


def enumerate_pg_query_keys(rows: List[Dict[str, Any]]) -> Tuple[Tuple[str, str, str, str], ...]:
    out: List[Tuple[str, str, str, str]] = []
    seen: Set[Tuple[str, str, str, str]] = set()
    for row in rows:
        tin = (row.get("text_in") or "").strip()
        need_ru, need_en = _needs_ru_en(row)
        if not tin or not (need_ru or need_en):
            continue
        sl = detect_lang(tin)
        for txt in _text_variants(tin):
            for dom_pg in _domains_for(row):
                if need_ru:
                    t = (txt, sl, dom_pg, "ru")
                    if t not in seen:
                        seen.add(t)
                        out.append(t)
                if need_en:
                    te = (txt, sl, dom_pg, "en")
                    if te not in seen:
                        seen.add(te)
                        out.append(te)
    return tuple(out)


def fill_rows_from_pg_matrix(rows: List[Dict[str, Any]], hit_matrix: Dict[Tuple[str, str, str, str], str]) -> Tuple[int, int]:
    """Заполняет пустые ru/en из накопленной матрицы; ru → source_ru=postgres_term_cache."""
    hr = he = 0
    for row in rows:
        tin = (row.get("text_in") or "").strip()
        need_ru, need_en = _needs_ru_en(row)
        if not tin or not (need_ru or need_en):
            continue
        sl = detect_lang(tin)

        if need_ru:
            got_ru = ""
            for txt in _text_variants(tin):
                if got_ru:
                    break
                for dom_pg in _domains_for(row):
                    cand = hit_matrix.get((txt, sl, dom_pg, "ru"))
                    if cand:
                        got_ru = cand.strip()
                        break
            if got_ru:
                row["ru"] = got_ru
                row["source_ru"] = "postgres_term_cache"
                hr += 1

        if not (row.get("en") or "").strip():
            got_en = ""
            for txt in _text_variants(tin):
                if got_en:
                    break
                for dom_pg in _domains_for(row):
                    cand = hit_matrix.get((txt, sl, dom_pg, "en"))
                    if cand:
                        got_en = cand.strip()
                        break
            if got_en:
                row["en"] = got_en
                he += 1

    return hr, he


async def enrich_rows_pg_term_cache(
    pool: Any,
    rows: List[Dict[str, Any]],
    *,
    timeout_sec: float,
    max_keys: int,
    max_rounds: int,
) -> CatalogEnrichPgOutcome:
    if not rows:
        return CatalogEnrichPgOutcome(0, 0, 0, False, 0)

    keys_planned_full = enumerate_pg_query_keys(rows)
    planned_set = set(keys_planned_full)
    if not planned_set:
        return CatalogEnrichPgOutcome(0, 0, 0, False, 0)

    sql = """
SELECT t.source_text, t.source_lang, t.domain, t.target_lang, t.translated_text
FROM term_translation_cache AS t
INNER JOIN unnest($1::text[], $2::text[], $3::text[], $4::text[])
  AS q(st, sl, dom, tg)
  ON t.source_text = q.st
 AND t.source_lang = q.sl
 AND t.domain = q.dom
 AND t.target_lang = q.tg
"""

    hit_matrix: Dict[Tuple[str, str, str, str], str] = {}
    queried: Set[Tuple[str, str, str, str]] = set()
    total_q = 0
    rnd_done = 0

    async def _fetch_arrays(
        sts: List[str],
        sls: List[str],
        doms: List[str],
        tg: List[str],
    ) -> List[Any]:
        async def _fetch() -> List[Any]:
            async with pool.acquire() as conn:
                return await conn.fetch(sql, sts, sls, doms, tg)

        return await asyncio.wait_for(_fetch(), timeout=max(0.2, timeout_sec))

    for rnd in range(max(1, max_rounds)):
        batch: List[Tuple[str, str, str, str]] = []
        for k in keys_planned_full:
            if k not in queried:
                batch.append(k)
                if len(batch) >= max_keys:
                    break
        if not batch:
            break

        sts = [b[0] for b in batch]
        sls = [b[1] for b in batch]
        doms = [b[2] for b in batch]
        tgs = [b[3] for b in batch]

        try:
            recs = await _fetch_arrays(sts, sls, doms, tgs)
        except (asyncio.TimeoutError, Exception) as exc:
            _log.warning("catalog enrich pg round %s failed (degraded): %s", rnd, exc)
            inc_cache_lookup("catalog_enrich_pg_batch", hit=False)
            hr, he = fill_rows_from_pg_matrix(rows, hit_matrix)
            truncated = bool(planned_set - queried)
            return CatalogEnrichPgOutcome(hr, he, total_q, truncated, rnd_done)

        queried.update(batch)
        total_q += len(batch)
        rnd_done = rnd + 1

        for r in recs:
            st = str(r["source_text"] or "").strip()
            sl_row = str(r["source_lang"] or "").strip()
            dom_row = str(r["domain"] or "").strip()
            tg_row = str(r["target_lang"] or "").strip()
            txt_out = str(r["translated_text"] or "").strip()
            if st and tg_row in {"ru", "en"} and txt_out:
                hit_matrix[(st, sl_row, dom_row, tg_row)] = txt_out

    truncated = bool(planned_set - queried)
    hr, he = fill_rows_from_pg_matrix(rows, hit_matrix)
    inc_cache_lookup("catalog_enrich_pg_batch", hit=bool(hr or he))
    return CatalogEnrichPgOutcome(hr, he, total_q, truncated, rnd_done)
