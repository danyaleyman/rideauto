#!/usr/bin/env python3
"""Раннер SQL-миграций PostgreSQL для RideAuto.

Зачем: миграции в ``infrastructure/postgresql/migrations/`` раньше применялись вручную
(``psql -f``), без учёта применённых и без защиты от дрейфа. Этот раннер ведёт таблицу
``schema_migrations`` (применённые версии + контрольная сумма) и предоставляет CLI.

Команды:
  status     — показать применённые и ожидающие миграции (read-only).
  apply      — применить все ожидающие миграции (каждая в своей транзакции).
  check      — exit 1, если есть ожидающие миграции ИЛИ дрейф контрольных сумм (для CI).
  rollback   — откатить применённую миграцию по ``.down.sql`` (см. 008_*.down.sql)
  baseline   — пометить текущие файлы применёнными БЕЗ выполнения SQL
               (адаптация раннера на существующей БД, где схема уже накатана вручную).

DSN берётся из (по приоритету): --dsn, $MIGRATE_DSN, $WRA_PG_DSN, $DATABASE_URL.

Примеры:
  python infrastructure/postgresql/migrate.py status
  python infrastructure/postgresql/migrate.py apply
  MIGRATE_DSN=postgresql://wra:***@127.0.0.1:5432/wra python .../migrate.py check
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

MIGRATIONS_DIRNAME = "migrations"
TRACKING_TABLE = "schema_migrations"
_FILENAME_RE = re.compile(r"^(?P<num>\d{3,})_(?P<slug>[a-z0-9][a-z0-9_]*)\.sql$")


@dataclass(frozen=True)
class Migration:
    version: str  # stem без .sql, например "002_encar_listing_flags"
    number: int  # числовой префикс для сортировки
    filename: str
    path: Path
    checksum: str  # sha256 hex от байт файла

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def down_path(self) -> Path:
        return self.path.with_name(f"{self.version}.down.sql")

    def has_downgrade(self) -> bool:
        return self.down_path().is_file()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_migrations(migrations_dir: Path) -> list[Migration]:
    """Считать и валидировать файлы миграций, отсортировать по числовому префиксу."""
    if not migrations_dir.is_dir():
        raise FileNotFoundError(f"migrations dir not found: {migrations_dir}")
    out: list[Migration] = []
    seen_numbers: dict[int, str] = {}
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name.endswith(".down.sql"):
            continue
        m = _FILENAME_RE.match(path.name)
        if not m:
            raise ValueError(
                f"bad migration filename {path.name!r}: expected NNN_slug.sql "
                f"(3+ digits, lowercase slug)"
            )
        number = int(m.group("num"))
        if number in seen_numbers:
            raise ValueError(
                f"duplicate migration number {number:03d}: "
                f"{seen_numbers[number]} and {path.name}"
            )
        seen_numbers[number] = path.name
        out.append(
            Migration(
                version=path.stem,
                number=number,
                filename=path.name,
                path=path,
                checksum=_sha256_file(path),
            )
        )
    out.sort(key=lambda mig: mig.number)
    return out


@dataclass(frozen=True)
class MigrationPlan:
    pending: list[Migration]
    drift: list[str]  # человекочитаемые описания расхождений
    applied_versions: set[str]


def plan_migrations(
    discovered: list[Migration], applied: dict[str, str]
) -> MigrationPlan:
    """Сопоставить файлы с применёнными версиями.

    ``applied``: version -> checksum (из таблицы schema_migrations).
    Дрейф: применённая версия, у которой контрольная сумма файла изменилась,
    или применённая версия, для которой файла больше нет.
    """
    discovered_by_version = {m.version: m for m in discovered}
    drift: list[str] = []
    pending: list[Migration] = []

    for version, checksum in sorted(applied.items()):
        mig = discovered_by_version.get(version)
        if mig is None:
            drift.append(f"applied migration {version!r} has no file on disk")
        elif mig.checksum != checksum:
            drift.append(
                f"checksum mismatch for {version!r}: "
                f"db={checksum[:12]}… file={mig.checksum[:12]}… "
                f"(applied migrations must be immutable)"
            )

    for mig in discovered:
        if mig.version not in applied:
            pending.append(mig)

    return MigrationPlan(pending=pending, drift=drift, applied_versions=set(applied))


# --- DB layer (psycopg2) -----------------------------------------------------


def resolve_dsn(explicit: Optional[str]) -> str:
    for candidate in (
        explicit,
        os.environ.get("MIGRATE_DSN"),
        os.environ.get("WRA_PG_DSN"),
        os.environ.get("DATABASE_URL"),
    ):
        s = (candidate or "").strip()
        if s:
            return s
    raise SystemExit(
        "no DSN: pass --dsn or set MIGRATE_DSN / WRA_PG_DSN / DATABASE_URL"
    )


def _connect(dsn: str):
    try:
        import psycopg2  # type: ignore
    except ImportError as exc:  # pragma: no cover - окружение без psycopg2
        raise SystemExit(
            "psycopg2 is required: pip install psycopg2-binary"
        ) from exc
    return psycopg2.connect(dsn)


def ensure_tracking_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TRACKING_TABLE} (
                version       TEXT PRIMARY KEY,
                filename      TEXT NOT NULL,
                checksum      TEXT NOT NULL,
                applied_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                execution_ms  INTEGER NOT NULL DEFAULT 0
            )
            """
        )
    conn.commit()


def fetch_applied(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT version, checksum FROM {TRACKING_TABLE}")
        return {row[0]: row[1] for row in cur.fetchall()}


def _record_applied(conn, mig: Migration, execution_ms: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {TRACKING_TABLE} (version, filename, checksum, execution_ms)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (version) DO UPDATE
                SET filename = EXCLUDED.filename,
                    checksum = EXCLUDED.checksum,
                    applied_at = now(),
                    execution_ms = EXCLUDED.execution_ms
            """,
            (mig.version, mig.filename, mig.checksum, execution_ms),
        )


def rollback_migration(conn, mig: Migration) -> int:
    """Выполнить ``{version}.down.sql`` и удалить запись из schema_migrations."""
    down = mig.down_path()
    if not down.is_file():
        raise FileNotFoundError(f"downgrade file not found: {down}")
    start = time.monotonic()
    sql = down.read_text(encoding="utf-8")
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(f"DELETE FROM {TRACKING_TABLE} WHERE version = %s", (mig.version,))
        elapsed = int((time.monotonic() - start) * 1000)
        conn.commit()
        return elapsed
    except Exception:
        conn.rollback()
        raise


def apply_migration(conn, mig: Migration) -> int:
    """Выполнить SQL миграции и записать факт в одной транзакции. Вернуть ms."""
    start = time.monotonic()
    try:
        with conn.cursor() as cur:
            cur.execute(mig.sql)
        elapsed = int((time.monotonic() - start) * 1000)
        _record_applied(conn, mig, elapsed)
        conn.commit()
        return elapsed
    except Exception:
        conn.rollback()
        raise


# --- CLI ---------------------------------------------------------------------


def _migrations_dir(arg: Optional[str]) -> Path:
    if arg:
        return Path(arg).resolve()
    return (Path(__file__).resolve().parent / MIGRATIONS_DIRNAME)


def _print_drift(drift: list[str]) -> None:
    print("DRIFT DETECTED:", file=sys.stderr)
    for d in drift:
        print(f"  - {d}", file=sys.stderr)


def cmd_status(args: argparse.Namespace) -> int:
    discovered = discover_migrations(_migrations_dir(args.migrations_dir))
    conn = _connect(resolve_dsn(args.dsn))
    try:
        ensure_tracking_table(conn)
        applied = fetch_applied(conn)
    finally:
        conn.close()
    p = plan_migrations(discovered, applied)
    print(f"discovered: {len(discovered)}  applied: {len(applied)}  pending: {len(p.pending)}")
    for mig in discovered:
        mark = "✓" if mig.version in p.applied_versions else "·"
        print(f"  [{mark}] {mig.filename}")
    if p.drift:
        _print_drift(p.drift)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    discovered = discover_migrations(_migrations_dir(args.migrations_dir))
    conn = _connect(resolve_dsn(args.dsn))
    try:
        ensure_tracking_table(conn)
        applied = fetch_applied(conn)
        p = plan_migrations(discovered, applied)
        if p.drift and not args.allow_drift:
            _print_drift(p.drift)
            print("refusing to apply with drift (use --allow-drift to override)", file=sys.stderr)
            return 1
        if not p.pending:
            print("nothing to apply (up to date)")
            return 0
        for mig in p.pending:
            print(f"applying {mig.filename} …", flush=True)
            ms = apply_migration(conn, mig)
            print(f"  done in {ms} ms")
        print(f"applied {len(p.pending)} migration(s)")
        return 0
    finally:
        conn.close()


def cmd_check(args: argparse.Namespace) -> int:
    discovered = discover_migrations(_migrations_dir(args.migrations_dir))
    conn = _connect(resolve_dsn(args.dsn))
    try:
        ensure_tracking_table(conn)
        applied = fetch_applied(conn)
    finally:
        conn.close()
    p = plan_migrations(discovered, applied)
    failed = False
    if p.drift:
        _print_drift(p.drift)
        failed = True
    if p.pending:
        print("PENDING MIGRATIONS:", file=sys.stderr)
        for mig in p.pending:
            print(f"  - {mig.filename}", file=sys.stderr)
        failed = True
    if failed:
        return 1
    print("ok: schema up to date, no drift")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    discovered = discover_migrations(_migrations_dir(args.migrations_dir))
    conn = _connect(resolve_dsn(args.dsn))
    try:
        ensure_tracking_table(conn)
        applied = fetch_applied(conn)
        applied_migs = sorted(
            [m for m in discovered if m.version in applied],
            key=lambda m: m.number,
            reverse=True,
        )
        if not applied_migs:
            print("nothing applied to rollback")
            return 0

        targets: list[Migration] = []
        if args.version:
            mig = next((m for m in discovered if m.version == args.version), None)
            if mig is None:
                print(f"unknown migration version: {args.version}", file=sys.stderr)
                return 1
            if mig.version not in applied:
                print(f"migration not applied: {args.version}", file=sys.stderr)
                return 1
            targets = [mig]
        else:
            steps = max(1, int(args.steps))
            for mig in applied_migs:
                if mig.has_downgrade():
                    targets.append(mig)
                if len(targets) >= steps:
                    break
            if len(targets) < steps:
                print(
                    f"only {len(targets)} rollback script(s) available (requested {steps})",
                    file=sys.stderr,
                )
                if not targets:
                    return 1

        for mig in targets:
            print(f"rolling back {mig.filename} using {mig.down_path().name} …", flush=True)
            ms = rollback_migration(conn, mig)
            print(f"  done in {ms} ms")
        print(f"rolled back {len(targets)} migration(s)")
        return 0
    finally:
        conn.close()


def cmd_baseline(args: argparse.Namespace) -> int:
    discovered = discover_migrations(_migrations_dir(args.migrations_dir))
    conn = _connect(resolve_dsn(args.dsn))
    try:
        ensure_tracking_table(conn)
        applied = fetch_applied(conn)
        to_mark = [m for m in discovered if m.version not in applied]
        if args.upto is not None:
            to_mark = [m for m in to_mark if m.number <= args.upto]
        if not to_mark:
            print("nothing to baseline")
            return 0
        for mig in to_mark:
            _record_applied(conn, mig, 0)
            print(f"baselined {mig.filename}")
        conn.commit()
        print(f"baselined {len(to_mark)} migration(s) without executing SQL")
        return 0
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RideAuto PostgreSQL migration runner")
    parser.add_argument("--dsn", help="PostgreSQL DSN (override env)")
    parser.add_argument(
        "--migrations-dir",
        help="path to migrations dir (default: alongside this script)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show applied/pending").set_defaults(func=cmd_status)

    p_apply = sub.add_parser("apply", help="apply pending migrations")
    p_apply.add_argument("--allow-drift", action="store_true", help="apply even if drift detected")
    p_apply.set_defaults(func=cmd_apply)

    sub.add_parser("check", help="exit 1 if pending or drift (CI gate)").set_defaults(func=cmd_check)

    p_rb = sub.add_parser("rollback", help="rollback applied migration(s) via .down.sql")
    p_rb.add_argument("--steps", type=int, default=1, help="how many recent applied migrations with .down.sql")
    p_rb.add_argument("--version", help="exact migration version stem, e.g. 008_catalog_dedupe_canonical")
    p_rb.set_defaults(func=cmd_rollback)

    p_base = sub.add_parser("baseline", help="mark files applied without running SQL")
    p_base.add_argument("--upto", type=int, help="only baseline up to this number (inclusive)")
    p_base.set_defaults(func=cmd_baseline)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
