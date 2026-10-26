#!/usr/bin/env python3
"""Fill Korea (Encar) HP + N·m from listing text, sibling consensus, engine_map.

Does not call DeepSeek / any LLM. After writes, cars.needs_pricing_recompute is
set so postgres_catalog_sync can upgrade korea_land_only → full_customs.

    python backend/scripts/backfill_korea_power_torque.py --stats-only
    python backend/scripts/backfill_korea_power_torque.py --batch-size 2000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from korea_power_torque import (  # noqa: E402
    KoreaPowerConsensus,
    apply_hp_torque,
    extract_hp_torque_from_payload,
    parse_hp,
    parse_nm,
    thin_row_to_payload_stub,
)

DEFAULT_SOURCES = ("encar", "korea")


def _dsn(args_dsn: str) -> str:
    return (args_dsn or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN") or "").strip()


def _source_sql(sources: List[str]) -> tuple[str, list[Any]]:
    if not sources or sources == ["*"]:
        return "", []
    placeholders = ",".join(["%s"] * len(sources))
    return f"AND source IN ({placeholders})", list(sources)


def _load_thin_rows(cur: Any, sources: List[str]) -> list[dict]:
    extra, params = _source_sql(sources)
    cur.execute(
        f"""
        SELECT
            id, car_id, mark, model, encar_model_group, generation, trim_name,
            fuel_type, displacement_cc, year, year_month, power_hp, torque_nm,
            NULLIF(TRIM(COALESCE(
                data #>> '{{data,extra,inspection,master,detail,motorType}}',
                data #>> '{{extra,inspection,master,detail,motorType}}',
                ''
            )), '') AS motor_code
        FROM cars
        WHERE 1=1
          {extra}
        ORDER BY id ASC
        """,
        tuple(params),
    )
    return [dict(r) for r in cur.fetchall()]


def _harvest_json_listing_text(
    conn: Any,
    sources: List[str],
    rows_by_id: Dict[int, dict],
) -> Dict[int, tuple[Optional[int], Optional[int], str]]:
    """Pull explicit 마력 / N·m / kg·m out of listing JSON for rows still missing values."""
    extra, params = _source_sql(sources)
    hits: Dict[int, tuple[Optional[int], Optional[int], str]] = {}
    scanned = 0
    with conn.cursor(name="korea_hp_json_scan", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.itersize = 500
        cur.execute(
            f"""
            SELECT id, data, power_hp, torque_nm
            FROM cars
            WHERE 1=1
              {extra}
              AND (
                power_hp IS NULL OR power_hp <= 0
                OR torque_nm IS NULL OR torque_nm <= 0
              )
            ORDER BY id ASC
            """,
            tuple(params),
        )
        while True:
            chunk = cur.fetchmany(500)
            if not chunk:
                break
            scanned += len(chunk)
            for rec in chunk:
                rid = int(rec["id"])
                payload = rec.get("data")
                if isinstance(payload, (bytes, memoryview)):
                    try:
                        payload = json.loads(bytes(payload).decode("utf-8", errors="replace"))
                    except Exception:
                        continue
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                if not isinstance(payload, dict):
                    continue
                hp, nm, src = extract_hp_torque_from_payload(payload)
                if hp is None and nm is None:
                    continue
                if parse_hp(rec.get("power_hp")) is not None:
                    hp = None
                if parse_nm(rec.get("torque_nm")) is not None:
                    nm = None
                if hp is None and nm is None:
                    continue
                hits[rid] = (hp, nm, src or "listing_text")
                row = rows_by_id.get(rid)
                if row is not None:
                    if hp is not None:
                        row["power_hp"] = hp
                    if nm is not None:
                        row["torque_nm"] = nm
            if scanned % 20_000 < 500:
                print(f"  … json scan scanned={scanned} listing_hits={len(hits)}", flush=True)
    print(f"json listing harvest scanned={scanned} hits={len(hits)}", flush=True)
    return hits


def _build_consensus(rows: list[dict]) -> KoreaPowerConsensus:
    table = KoreaPowerConsensus()
    for row in rows:
        stub = thin_row_to_payload_stub(row)
        hp = parse_hp(row.get("power_hp"))
        nm = parse_nm(row.get("torque_nm"))
        text_hp, text_nm, _src = extract_hp_torque_from_payload(stub)
        if hp is None:
            hp = text_hp
        if nm is None:
            nm = text_nm
        if hp is not None or nm is not None:
            table.add_observation(stub, hp=hp, nm=nm)
    return table


def _plan_updates(rows: list[dict], table: KoreaPowerConsensus) -> list[dict]:
    planned: list[dict] = []
    for row in rows:
        stub = thin_row_to_payload_stub(row)
        have_hp = parse_hp(row.get("power_hp"))
        have_nm = parse_nm(row.get("torque_nm"))
        hit = table.resolve(stub)
        need_hp = have_hp is None and hit.hp is not None
        need_nm = have_nm is None and hit.nm is not None
        if not need_hp and not need_nm:
            continue
        planned.append(
            {
                "id": int(row["id"]),
                "hp": hit.hp if need_hp else have_hp,
                "nm": hit.nm if need_nm else have_nm,
                "source": hit.source or "peer_year",
                "set_hp": need_hp,
                "set_nm": need_nm,
            }
        )
    return planned


def _merge_payload(payload: Any, item: dict) -> Optional[dict]:
    if isinstance(payload, (bytes, memoryview)):
        try:
            payload = json.loads(bytes(payload).decode("utf-8", errors="replace"))
        except Exception:
            return None
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    apply_hp_torque(
        payload,
        hp=item["hp"] if item["set_hp"] else None,
        nm=item["nm"] if item["set_nm"] else None,
        source=item["source"],
    )
    return payload


def _apply_batch(cur: Any, items: list[dict], dry_run: bool) -> tuple[int, int]:
    if not items:
        return 0, 0
    ids = [int(x["id"]) for x in items]
    cur.execute(
        "SELECT id, data, power_hp, torque_nm FROM cars WHERE id = ANY(%s)",
        (ids,),
    )
    by_id = {int(r["id"]): r for r in cur.fetchall()}
    updated = 0
    skipped = 0
    for item in items:
        rec = by_id.get(int(item["id"]))
        if rec is None:
            skipped += 1
            continue
        payload = _merge_payload(rec["data"], item)
        if payload is None:
            skipped += 1
            continue
        new_hp = item["hp"] if item["set_hp"] else parse_hp(rec.get("power_hp"))
        new_nm = item["nm"] if item["set_nm"] else parse_nm(rec.get("torque_nm"))
        if dry_run:
            updated += 1
            continue
        cur.execute(
            """
            UPDATE cars
            SET data = %s,
                power_hp = COALESCE(%s, power_hp),
                torque_nm = COALESCE(%s, torque_nm),
                needs_pricing_recompute = TRUE,
                updated_at = now()
            WHERE id = %s
            """,
            (
                psycopg2.extras.Json(payload),
                int(new_hp) if new_hp is not None else None,
                int(new_nm) if new_nm is not None else None,
                int(item["id"]),
            ),
        )
        updated += 1
    return updated, skipped


def main() -> int:
    p = argparse.ArgumentParser(description="Korea observed HP + N·m backfill (no LLM)")
    p.add_argument("--dsn", default="")
    p.add_argument("--source", default="encar,korea", help="comma sources, or *")
    p.add_argument("--batch-size", type=int, default=2000)
    p.add_argument("--max-rows", type=int, default=0, help="Cap planned updates (0 = all)")
    p.add_argument("--stats-only", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--scan-json", action="store_true", help="Also harvest 마력/토크 from listing JSON")
    args = p.parse_args()

    dsn = _dsn(args.dsn)
    if not dsn:
        print("PostgreSQL DSN is required: --dsn or DATABASE_URL/WRA_PG_DSN", file=sys.stderr)
        return 2

    sources = [s.strip() for s in str(args.source).split(",") if s.strip()]
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    done = 0
    skipped = 0
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            print("loading thin korea rows…", flush=True)
            rows = _load_thin_rows(cur, sources)
        print(f"loaded rows={len(rows)}", flush=True)
        rows_by_id = {int(r["id"]): r for r in rows}
        with_motor = sum(1 for r in rows if r.get("motor_code"))
        print(f"rows_with_motor_code={with_motor}", flush=True)
        if args.scan_json:
            _harvest_json_listing_text(conn, sources, rows_by_id)
        table = _build_consensus(rows)
        print(f"consensus observations={table.observations}", flush=True)
        preview = table.coverage_preview(thin_row_to_payload_stub(r) for r in rows)
        print("coverage " + " ".join(f"{k}={v}" for k, v in sorted(preview.items())), flush=True)
        if args.stats_only:
            conn.rollback()
            return 0

        planned = _plan_updates(rows, table)
        if args.max_rows > 0:
            planned = planned[: args.max_rows]
        print(f"planned updates={len(planned)} dry_run={int(args.dry_run)}", flush=True)

        batch = max(100, int(args.batch_size))
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for i in range(0, len(planned), batch):
                chunk = planned[i : i + batch]
                u, s = _apply_batch(cur, chunk, dry_run=args.dry_run)
                done += u
                skipped += s
                if not args.dry_run:
                    conn.commit()
                else:
                    conn.rollback()
                print(
                    f"progress updated={done} skipped={skipped} last_id={chunk[-1]['id']}",
                    flush=True,
                )
    finally:
        conn.close()

    print(f"done updated={done} skipped={skipped}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
