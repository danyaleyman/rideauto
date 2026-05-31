"""Тесты чистой логики раннера миграций (без БД): discovery + planning + drift."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MIGRATE_PY = _REPO_ROOT / "infrastructure" / "postgresql" / "migrate.py"


def _load_migrate():
    spec = importlib.util.spec_from_file_location("rideauto_migrate", _MIGRATE_PY)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass требует модуль в sys.modules
    spec.loader.exec_module(mod)
    return mod


migrate = _load_migrate()


def _write(dir_: Path, name: str, body: str) -> None:
    (dir_ / name).write_text(body, encoding="utf-8")


def test_migrate_py_exists() -> None:
    assert _MIGRATE_PY.is_file()


def test_real_migrations_discover_and_sort() -> None:
    real_dir = _REPO_ROOT / "infrastructure" / "postgresql" / "migrations"
    migs = migrate.discover_migrations(real_dir)
    assert migs, "expected real migration files"
    numbers = [m.number for m in migs]
    assert numbers == sorted(numbers)
    assert len(numbers) == len(set(numbers)), "duplicate migration numbers in repo"
    # checksum стабилен и непустой
    assert all(len(m.checksum) == 64 for m in migs)


def test_discover_rejects_bad_filename(tmp_path: Path) -> None:
    _write(tmp_path, "001_ok.sql", "SELECT 1;")
    _write(tmp_path, "bad_name.sql", "SELECT 1;")
    with pytest.raises(ValueError, match="bad migration filename"):
        migrate.discover_migrations(tmp_path)


def test_discover_rejects_duplicate_number(tmp_path: Path) -> None:
    _write(tmp_path, "001_a.sql", "SELECT 1;")
    _write(tmp_path, "001_b.sql", "SELECT 1;")
    with pytest.raises(ValueError, match="duplicate migration number"):
        migrate.discover_migrations(tmp_path)


def test_plan_pending_and_applied(tmp_path: Path) -> None:
    _write(tmp_path, "001_a.sql", "SELECT 1;")
    _write(tmp_path, "002_b.sql", "SELECT 2;")
    _write(tmp_path, "003_c.sql", "SELECT 3;")
    migs = migrate.discover_migrations(tmp_path)
    applied = {migs[0].version: migs[0].checksum}  # только первая
    plan = migrate.plan_migrations(migs, applied)
    assert [m.version for m in plan.pending] == [migs[1].version, migs[2].version]
    assert plan.drift == []


def test_plan_detects_checksum_drift(tmp_path: Path) -> None:
    _write(tmp_path, "001_a.sql", "SELECT 1;")
    migs = migrate.discover_migrations(tmp_path)
    applied = {migs[0].version: "deadbeef" * 8}  # другая сумма
    plan = migrate.plan_migrations(migs, applied)
    assert plan.pending == []
    assert any("checksum mismatch" in d for d in plan.drift)


def test_plan_detects_missing_file_drift(tmp_path: Path) -> None:
    _write(tmp_path, "001_a.sql", "SELECT 1;")
    migs = migrate.discover_migrations(tmp_path)
    applied = {
        migs[0].version: migs[0].checksum,
        "999_ghost": "ab" * 32,
    }
    plan = migrate.plan_migrations(migs, applied)
    assert any("no file on disk" in d for d in plan.drift)


def test_resolve_dsn_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIGRATE_DSN", raising=False)
    monkeypatch.delenv("WRA_PG_DSN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    assert migrate.resolve_dsn(None) == "postgresql://x/y"
    assert migrate.resolve_dsn("postgresql://explicit/z") == "postgresql://explicit/z"
    monkeypatch.setenv("WRA_PG_DSN", "postgresql://wra/db")
    assert migrate.resolve_dsn(None) == "postgresql://wra/db"


def test_migration_down_path(tmp_path: Path) -> None:
    _write(tmp_path, "008_catalog_dedupe_canonical.sql", "SELECT 1;")
    _write(tmp_path, "008_catalog_dedupe_canonical.down.sql", "DROP COLUMN x;")
    migs = migrate.discover_migrations(tmp_path)
    assert len(migs) == 1
    assert migs[0].has_downgrade()
    assert migs[0].down_path().name.endswith(".down.sql")


def test_resolve_dsn_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIGRATE_DSN", raising=False)
    monkeypatch.delenv("WRA_PG_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit):
        migrate.resolve_dsn(None)
