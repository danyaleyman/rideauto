#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


def _postgres_dsn(config_path: Path) -> str:
    try:
        import yaml  # type: ignore
    except Exception:
        yaml = None
    if yaml and config_path.is_file():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            dsn = str((((cfg.get("storage") or {}).get("postgres") or {}).get("dsn") or "")).strip()
            if dsn:
                return dsn
        except Exception:
            pass
    return (os.environ.get("DATABASE_URL") or "").strip()


def _decode_raw(raw_obj: Any) -> Dict[str, Any]:
    if not isinstance(raw_obj, dict):
        return {}
    enc = str(raw_obj.get("encoding") or "")
    if enc == "gzip+base64+json":
        blob = str(raw_obj.get("blob") or "")
        if not blob:
            return {}
        try:
            dec = gzip.decompress(base64.b64decode(blob.encode("ascii")))
            parsed = json.loads(dec.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return raw_obj if "sources" in raw_obj else {}


def _fingerprint(data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _fetch_rows(
    dsn: str,
    limit: int,
    car_ids: Sequence[str],
    *,
    source: str,
) -> List[Tuple[int, str, Dict[str, Any], Dict[str, Any]]]:
    import psycopg2
    import psycopg2.extras

    src = str(source or "encar").strip().lower()
    if car_ids:
        q = """
        SELECT id, car_id, data, raw
        FROM cars
        WHERE lower(trim(source)) = %s
          AND car_id = ANY(%s)
        ORDER BY updated_at DESC
        """
        params = (src, list(car_ids))
    else:
        q = """
        SELECT id, car_id, data, raw
        FROM cars
        WHERE lower(trim(source)) = %s
          AND raw IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT %s
        """
        params = (src, limit)
    out: List[Tuple[int, str, Dict[str, Any], Dict[str, Any]]] = []
    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, params)
            for row in cur.fetchall():
                data = row.get("data")
                raw = row.get("raw")
                if not isinstance(data, dict) or not isinstance(raw, dict):
                    continue
                out.append((int(row["id"]), str(row["car_id"]), data, raw))
    return out


def _che168_external_id(car_id: str) -> str:
    s = str(car_id).strip()
    low = s.lower()
    if low.startswith("che168-"):
        return s[7:]
    return s


def _update_data(dsn: str, row_id: int, data: Dict[str, Any]) -> None:
    import psycopg2

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE cars SET data=%s::jsonb, needs_pricing_recompute = TRUE, updated_at=now() WHERE id=%s",
                (json.dumps(data, ensure_ascii=False), row_id),
            )
        conn.commit()


def main() -> None:
    p = argparse.ArgumentParser(description="Reprocess cars.data from stored raw envelope")
    p.add_argument("--config", default="scraper_config.yaml")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--car-id", action="append", default=[])
    p.add_argument("--source", default="encar", help="encar | che168")
    p.add_argument(
        "--che168-assume-wan-yuan",
        action="store_true",
        help="Che168: interpret small floats as 万元 (see scraper assume_price_in_wan_yuan)",
    )
    p.add_argument("--apply", action="store_true", help="Write updated normalized data to DB")
    args = p.parse_args()

    dsn = _postgres_dsn(Path(args.config).expanduser().resolve())
    if not dsn:
        raise SystemExit("DATABASE_URL/storage.postgres.dsn is empty")

    source = str(args.source or "encar").strip().lower()
    rows = _fetch_rows(
        dsn,
        limit=max(1, args.limit),
        car_ids=[str(x).strip() for x in args.car_id if str(x).strip()],
        source=source,
    )
    stats = {"checked": 0, "reprocessed": 0, "changed": 0, "updated": 0, "no_raw_sources": 0, "source": source}
    encar_parser = None
    if source != "che168":
        from parser_full import EncarFullParser

        encar_parser = EncarFullParser()
    for row_id, car_id, current_data, raw_db in rows:
        stats["checked"] += 1
        envelope = _decode_raw(raw_db)
        src = envelope.get("sources") if isinstance(envelope, dict) else None
        if not isinstance(src, dict):
            stats["no_raw_sources"] += 1
            continue
        if source == "che168":
            from scraper_pipeline.che168.parser import parse_one_che168_car_sync

            list_item = src.get("list_item") if isinstance(src.get("list_item"), dict) else {}
            carinfo = src.get("carinfo") if isinstance(src.get("carinfo"), dict) else None
            specparam = src.get("specparam") if isinstance(src.get("specparam"), dict) else None
            specconfig = src.get("specconfig") if isinstance(src.get("specconfig"), dict) else None
            recommend = src.get("recommend") if isinstance(src.get("recommend"), dict) else None
            report_summary = src.get("report_summary") if isinstance(src.get("report_summary"), dict) else None
            out = parse_one_che168_car_sync(
                external_id=_che168_external_id(car_id),
                list_item=list_item,
                carinfo=carinfo,
                specparam=specparam,
                specconfig=specconfig,
                recommend=recommend,
                report_summary=report_summary,
                assume_price_wan_yuan=bool(args.che168_assume_wan_yuan),
                source_meta=(envelope.get("source_meta") if isinstance(envelope.get("source_meta"), dict) else None),
            )
        else:
            from scraper_pipeline.encar.parser import parse_one_car_sync

            item = src.get("list_item") if isinstance(src.get("list_item"), dict) else {}
            detail = src.get("detail") if isinstance(src.get("detail"), dict) else {}
            diagnosis = src.get("diagnosis") if isinstance(src.get("diagnosis"), dict) else {}
            record = src.get("record") if isinstance(src.get("record"), dict) else {}
            inspection = src.get("inspection") if isinstance(src.get("inspection"), dict) else {}
            sellingpoint = src.get("sellingpoint") if isinstance(src.get("sellingpoint"), dict) else {}
            user_info = src.get("user") if isinstance(src.get("user"), dict) else {}
            out = parse_one_car_sync(
                parser=encar_parser,
                car_id=car_id,
                item=item,
                detail=detail,
                diagnosis=diagnosis,
                record=record,
                inspection=inspection,
                sellingpoint=sellingpoint,
                user_info=user_info,
                source_meta=(envelope.get("source_meta") if isinstance(envelope.get("source_meta"), dict) else None),
            )
        if not out or not isinstance(out.get("data"), dict):
            continue
        stats["reprocessed"] += 1
        new_data = out["data"]
        old_fp = _fingerprint(current_data)
        new_fp = _fingerprint(new_data)
        if old_fp != new_fp:
            stats["changed"] += 1
            if args.apply:
                _update_data(dsn, row_id=row_id, data=new_data)
                stats["updated"] += 1
    print(json.dumps(stats, ensure_ascii=False))
    raise SystemExit(0)


if __name__ == "__main__":
    main()

