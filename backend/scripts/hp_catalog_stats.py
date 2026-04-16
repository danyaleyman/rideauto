#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from hp_catalog_store import DEFAULT_DB_PATH, connect, ensure_schema


def main() -> int:
    p = argparse.ArgumentParser(description="Show hp_catalog fill progress")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to hp_catalog.db")
    args = p.parse_args()

    conn = connect(args.db)
    ensure_schema(conn)

    total = conn.execute("SELECT COUNT(*) FROM hp_catalog").fetchone()[0]
    with_hp = conn.execute("SELECT COUNT(*) FROM hp_catalog WHERE power_hp IS NOT NULL AND power_hp > 0").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM hp_catalog WHERE (power_hp IS NULL OR power_hp <= 0) AND llm_status='pending'").fetchone()[0]
    no_data = conn.execute("SELECT COUNT(*) FROM hp_catalog WHERE (power_hp IS NULL OR power_hp <= 0) AND llm_status='no_data'").fetchone()[0]
    errors = conn.execute("SELECT COUNT(*) FROM hp_catalog WHERE (power_hp IS NULL OR power_hp <= 0) AND llm_status='error'").fetchone()[0]
    conn.close()

    pct = (float(with_hp) / float(total) * 100.0) if total else 0.0
    print(f"db={args.db}")
    print(f"total={total}")
    print(f"with_hp={with_hp} ({pct:.2f}%)")
    print(f"pending={pending}")
    print(f"no_data={no_data}")
    print(f"errors={errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
