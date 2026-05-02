#!/usr/bin/env python3
"""
Пайплайн: PostgreSQL (машины без power_hp в строке каталога)
→ уникальные ключи в hp_catalog.db (pending)
→ DeepSeek / OpenAI заполняет hp
→ postgres_catalog_sync заново обогащает JSONB `data`, колонку cars.power_hp и пересчитывает Encar-цены.

Автоматика: по крону или CI job; API «сам» не ходит в DeepSeek — нужен batch-скрипт + ключ.

Env (частые):
  HP_RECOVERY_LIGHT_SYNC=1  — добавить в postgres_catalog_sync флаг --no-meilisearch (или --light-catalog-sync).
  HP_RECOVERY_SYNC_EXTRA_ARGS / HP_RECOVERY_FILL_EXTRA_ARGS — проброс доп. CLI.
  DeepSeek backoff: HP_LLM_MAX_RETRIES, лимит вызовов: HP_LLM_MAX_CALLS_PER_RUN.
  Отключить LLM с пометкой review в резолвере: HP_CATALOG_SKIP_REVIEW_FLAGGED_LLM=1.
"""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_BACKEND = _REPO / "backend"
_SYNC_PG = _BACKEND / "scripts" / "sync_hp_catalog_from_postgres.py"
_FILL_LLM = _BACKEND / "scripts" / "fill_hp_catalog_deepseek.py"
_PG_SYNC = _BACKEND / "postgres_catalog_sync.py"


def _run(py: Path, args: list[str], *, cwd: Path) -> None:
    cmd = [sys.executable, str(py), *args]
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=str(cwd))
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Enqueue missing HP keys from Postgres → LLM fill hp_catalog.db → "
            "postgres_catalog_sync (power + price recalc)"
        ),
    )
    p.add_argument("--dsn", default="", help="PostgreSQL DSN (или DATABASE_URL / WRA_PG_DSN)")
    p.add_argument(
        "--hp-db",
        type=Path,
        default=None,
        help="Путь к hp_catalog.db (по умолчанию data/hp_catalog.db под репозиторием)",
    )
    p.add_argument("--source", default="encar", help="Фильтр cars.source для sync_hp_catalog (или *)")
    p.add_argument("--skip-enqueue", action="store_true", help="Не вызывать sync_hp_catalog_from_postgres")
    p.add_argument("--skip-llm", action="store_true", help="Не вызывать fill_hp_catalog_deepseek")
    p.add_argument("--skip-catalog-sync", action="store_true", help="Не запускать postgres_catalog_sync")
    p.add_argument("--max-llm-rows", type=int, default=0, help="Передать в fill ... --max-rows (0 = без лимита)")
    p.add_argument(
        "--catalog-sync-args",
        default="",
        help='Доп. аргументы к postgres_catalog_sync (строкой, например "--no-meilisearch")',
    )
    p.add_argument(
        "--light-catalog-sync",
        action="store_true",
        help="Подставляет --no-meilisearch для ночных прогонов (тяжёлый Meilisearch отдельно)",
    )
    args = p.parse_args()

    dsn = (args.dsn or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN") or "").strip()
    if not dsn and not args.skip_catalog_sync:
        print("PostgreSQL DSN обязателен для catalog sync (--dsn или DATABASE_URL/WRA_PG_DSN).", flush=True)
        return 2
    if not dsn and not args.skip_enqueue:
        print("DSN нужен для шага enqueue (sync_hp_catalog_from_postgres).", flush=True)
        return 2

    hp_db = Path(args.hp_db) if args.hp_db else _REPO / "data" / "hp_catalog.db"

    if not args.skip_enqueue:
        enq_args = ["--dsn", dsn, "--db", str(hp_db), "--only-missing-hp", "--source", args.source]
        _run(_SYNC_PG, enq_args, cwd=_REPO)

    if not args.skip_llm:
        llm_args = ["--db", str(hp_db)]
        if args.max_llm_rows > 0:
            llm_args.extend(["--max-rows", str(args.max_llm_rows)])
        extra = os.environ.get("HP_RECOVERY_FILL_EXTRA_ARGS", "").strip()
        if extra:
            llm_args.extend(extra.split())
        _run(_FILL_LLM, llm_args, cwd=_REPO)

    if not args.skip_catalog_sync:
        sync_args_list = ["--dsn", dsn]
        light_sync = (
            args.light_catalog_sync
            or str(os.environ.get("HP_RECOVERY_LIGHT_SYNC", "") or "").strip().lower()
            in ("1", "true", "yes", "on")
        )
        merged_extra: list[str] = []
        if args.catalog_sync_args.strip():
            merged_extra.extend(shlex.split(args.catalog_sync_args))
        extra_pg = os.environ.get("HP_RECOVERY_SYNC_EXTRA_ARGS", "").strip()
        if extra_pg:
            merged_extra.extend(shlex.split(extra_pg))
        if light_sync and not any(
            x == "--no-meilisearch" or str(x).startswith("--no-meilisearch")
            for x in merged_extra
        ):
            merged_extra.insert(0, "--no-meilisearch")
        if merged_extra:
            sync_args_list.extend(merged_extra)
        _run(_PG_SYNC, sync_args_list, cwd=_REPO)

    print("hp_recovery_pipeline: завершено.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
