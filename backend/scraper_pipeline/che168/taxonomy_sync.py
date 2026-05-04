"""Слияние таксономии Che168: GET /brand (официальные имена) + YAML-алиасы."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper_pipeline.che168.workers import _api_layer_list, che168_brand_id, che168_brand_rows


def _pick_brand_display_name(row: dict) -> Optional[str]:
    for k in ("name", "brandname", "brandName", "Name", "title", "showname", "showName"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _english_brand_alias(row: dict) -> Optional[str]:
    for k in ("englishname", "englishName", "enname", "enName", "ename", "eName"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def build_mark_aliases_from_brand_rows(rows: List[dict]) -> tuple[Dict[str, str], Dict[str, str]]:
    """
    mark_aliases: lowercase/ключ → каноническое имя как в API.
    brand_by_id: str(brandid) → каноническое имя.
    """
    mark_aliases: Dict[str, str] = {}
    brand_by_id: Dict[str, str] = {}
    for row in rows:
        bid = che168_brand_id(row)
        canonical = _pick_brand_display_name(row)
        if bid is None or not canonical:
            continue
        sid = str(bid)
        brand_by_id[sid] = canonical
        mark_aliases[canonical.lower()] = canonical
        for part in canonical.replace("·", " ").replace("/", " ").split():
            p = part.strip()
            if len(p) >= 2:
                mark_aliases[p.lower()] = canonical
        en = _english_brand_alias(row)
        if en:
            mark_aliases[en.lower()] = canonical
    return mark_aliases, brand_by_id


def merge_che168_taxonomy_with_brand_api(
    brand_payload: Any,
    yaml_taxonomy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Берёт дерево брендов из ответа /brand, строит brand_by_id и алиасы.
    YAML-алиасы (mark_aliases, model_aliases) накладываются поверх и перекрывают ключи API.
    """
    base: Dict[str, Any] = {}
    if isinstance(yaml_taxonomy, dict):
        if isinstance(yaml_taxonomy.get("mark_aliases"), dict):
            base["mark_aliases"] = dict(yaml_taxonomy["mark_aliases"])
        if isinstance(yaml_taxonomy.get("model_aliases"), dict):
            base["model_aliases"] = dict(yaml_taxonomy["model_aliases"])
    base.setdefault("mark_aliases", {})
    base.setdefault("model_aliases", {})

    rows = che168_brand_rows(brand_payload)
    api_marks, brand_by_id = build_mark_aliases_from_brand_rows(rows)

    merged_marks = {**api_marks, **base["mark_aliases"]}
    base["mark_aliases"] = merged_marks
    base["brand_by_id"] = {**brand_by_id, **dict(base.get("brand_by_id") or {})}
    if isinstance(yaml_taxonomy, dict) and isinstance(yaml_taxonomy.get("brand_by_id"), dict):
        base["brand_by_id"].update(
            {str(k): str(v).strip() for k, v in yaml_taxonomy["brand_by_id"].items() if v}
        )

    src = list(base.get("taxonomy_source") or [])
    if "che168_brand_api" not in src:
        src.append("che168_brand_api")
    base["taxonomy_source"] = src
    base["taxonomy_brand_row_count"] = len(rows)
    return base


def che168_series_rows(series_payload: Any) -> List[dict]:
    if not isinstance(series_payload, dict):
        return []
    layer = _api_layer_list(series_payload)
    for key in ("list", "serieslist", "seriesList", "rows", "items", "carserieslist"):
        v = layer.get(key)
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
    if isinstance(series_payload.get("list"), list):
        return [x for x in series_payload["list"] if isinstance(x, dict)]
    return []


def _series_id_from_row(row: dict) -> Optional[int]:
    for k in ("seriesid", "seriesId", "id", "Id", "sid", "serieid"):
        v = row.get(k)
        if v is None or str(v).strip() == "":
            continue
        s = str(v).strip()
        if s.isdigit():
            return int(s)
        try:
            n = int(float(s))
            return n if n > 0 else None
        except (TypeError, ValueError):
            continue
    return None


def _series_name_from_row(row: dict) -> Optional[str]:
    for k in ("name", "seriesname", "seriesName", "showname", "showName", "title"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def merge_series_for_brand_into_taxonomy(taxonomy: Dict[str, Any], brand_id: int, series_payload: Any) -> int:
    """Дополняет taxonomy: series_by_brandid, seriesid_to_model_name, model_aliases."""
    rows = che168_series_rows(series_payload)
    if not rows:
        return 0
    bkey = str(int(brand_id))
    bucket = taxonomy.setdefault("series_by_brandid", {})
    sidmap = taxonomy.setdefault("seriesid_to_model_name", {})
    malias = taxonomy.setdefault("model_aliases", {})

    slim: List[Dict[str, Any]] = []
    for row in rows:
        sid = _series_id_from_row(row)
        name = _series_name_from_row(row)
        if sid is None or not name:
            continue
        sids = str(sid)
        sidmap[sids] = name
        malias[name.lower()] = name
        for part in name.replace("·", " ").replace("/", " ").split():
            p = part.strip()
            if len(p) >= 2:
                malias[p.lower()] = name
        slim.append({"seriesid": sid, "name": name})
    if slim:
        bucket[bkey] = slim
    src = list(taxonomy.get("taxonomy_source") or [])
    if "che168_series_api" not in src:
        src.append("che168_series_api")
    taxonomy["taxonomy_source"] = src
    return len(slim)


_DEFAULT_SERIES_PATH_CANDIDATES = (
    "series",
    "carseries/serieslist",
    "common/serieslist",
    "GetSeriesList",
)


async def discover_che168_series_api_path(client: Any, config: dict, log: Any) -> bool:
    """
    Если `series_api_path` пуст, пробует `series_api_path_candidates` (или дефолтный список)
    на одном probe-бренде; при успехе выставляет `config['che168']['series_api_path']` в памяти.
    """
    from scraper_pipeline.che168.workers import _returncode_ok

    ch = config.setdefault("che168", {})
    if str(ch.get("series_api_path") or "").strip():
        return True
    tax = ch.get("taxonomy")
    if not isinstance(tax, dict) or not tax.get("brand_by_id"):
        return False
    try:
        bids = sorted({int(str(x)) for x in tax["brand_by_id"].keys()})
    except (TypeError, ValueError):
        return False
    if not bids:
        return False
    probe = ch.get("series_probe_brandid")
    bid = bids[0]
    if probe is not None and str(probe).strip() != "":
        try:
            pb = int(probe)
            if pb > 0:
                bid = pb
        except (TypeError, ValueError):
            pass

    raw_cands = ch.get("series_api_path_candidates")
    if raw_cands is None:
        cands = list(_DEFAULT_SERIES_PATH_CANDIDATES)
    elif isinstance(raw_cands, str):
        cands = [raw_cands]
    else:
        cands = list(raw_cands)
    cands = [str(c).strip().lstrip("/") for c in cands if str(c).strip()]

    for p in cands:
        if not p:
            continue
        raw, st, err = await client._request("GET", p, params={"brandid": int(bid)})
        if st != 200 or not raw or not _returncode_ok(raw):
            continue
        n_series = len(che168_series_rows(raw))
        ch["series_api_path"] = p
        log.info(
            "Che168 taxonomy: series_api_path автоматически выбран → %s (series_rows=%s probe_brandid=%s)",
            p,
            n_series,
            bid,
        )
        return True
    log.warning(
        "Che168 taxonomy: автопоиск series_api_path не нашёл рабочий путь; задайте che168.series_api_path вручную",
    )
    return False


async def sync_che168_series_taxonomy(client: Any, config: dict, log: Any) -> None:
    """После merge /brand — опционально GET series по каждому brandid (лимит запросов)."""
    from scraper_pipeline.che168.workers import _returncode_ok

    ch = config.get("che168", {}) or {}
    if not ch.get("taxonomy_sync_series", True):
        return
    await discover_che168_series_api_path(client, config, log)
    path = str((config.get("che168") or {}).get("series_api_path") or "").strip()
    if not path:
        return
    tax = ch.get("taxonomy")
    if not isinstance(tax, dict) or not tax.get("brand_by_id"):
        return
    max_b = max(1, int(ch.get("taxonomy_sync_series_max_brands", 50) or 50))
    delay = float(ch.get("taxonomy_sync_series_delay_sec", 0.15) or 0)
    bids_raw = list(tax["brand_by_id"].keys())
    try:
        bids = sorted({int(str(x)) for x in bids_raw})[:max_b]
    except (TypeError, ValueError):
        return
    import asyncio

    ok = 0
    fail = 0
    for bid in bids:
        raw, st, err = await client.fetch_series_for_brand(bid)
        if st == 200 and raw and _returncode_ok(raw):
            n = merge_series_for_brand_into_taxonomy(tax, bid, raw)
            if n:
                ok += 1
        else:
            fail += 1
            if fail <= 2:
                log.debug("Che168 series brand=%s status=%s err=%s", bid, st, err)
        if delay > 0:
            await asyncio.sleep(delay)
    log.info(
        "Che168 taxonomy: серии API — брендов с данными=%s из %s попыток (path=%s)",
        ok,
        len(bids),
        path,
    )
