#!/usr/bin/env python3
"""
Сброс «наследия»: строки LLM-каталога (source=catalog) в статусе done без llm_confidence.

После этого их снова обработает fill_hp_catalog_deepseek с новым промптом/порогом.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from hp_catalog_store import DEFAULT_DB_PATH, connect, ensure_schema
from power_from_external import invalidate_hp_catalog_cache


def main() -> int:
    p = argparse.ArgumentParser(description="Сброс done LLM-строк без llm_confidence обратно в pending")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    conn = connect(args.db)
    ensure_schema(conn)
    try:
        cur = conn.execute(
            """
            SELECT COUNT(*) FROM hp_catalog
            WHERE source = 'catalog'
              AND llm_status = 'done'
              AND llm_confidence IS NULL
              AND power_hp IS NOT NULL AND power_hp > 0
            """
        )
        n = int(cur.fetchone()[0])
        print(f"affected_candidates={n} dry_run={args.dry_run}", flush=True)
        if n == 0:
            return 0
        if args.dry_run:
            return 0
        conn.execute(
            """
            UPDATE hp_catalog
            SET power_hp=NULL, power_kw=NULL,
                llm_status='pending',
                llm_model='', llm_reason='',
                llm_prompt_version='', llm_prompt_hash='',
                review_flag=0, review_note='',
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            WHERE source = 'catalog'
              AND llm_status = 'done'
              AND llm_confidence IS NULL
              AND COALESCE(power_hp, 0) > 0
            """
        )
        conn.commit()
    finally:
        conn.close()

    invalidate_hp_catalog_cache()
    print("legacy_llm_rows reset to pending", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
