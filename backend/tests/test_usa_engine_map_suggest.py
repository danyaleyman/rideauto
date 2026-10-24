"""Tests for the USA HP-library growth loop (scripts/usa_engine_map_suggest.py).

Скрипт без БД: подменяем psycopg2 и lookup_vin_power, проверяем SQL-выборку,
сбор наблюдений из vPIC и запись кандидатов в us_engine_map.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import usa_engine_map_suggest as suggest


class _FakeCursor:
    def __init__(self, batches: list) -> None:
        self._batches = list(batches)
        self.executed: list = []

    def execute(self, sql: str, params=None) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list:
        return self._batches.pop(0) if self._batches else []

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class _FakeConn:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.closed = False

    def cursor(self, cursor_factory=None) -> _FakeCursor:
        return self._cursor

    def close(self) -> None:
        self.closed = True


class _FakePsycopg2:
    class extras:  # noqa: N801
        RealDictCursor = staticmethod(lambda *a, **kw: None)

    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def connect(self, dsn: str) -> _FakeConn:
        return self._conn


def test_dsn_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://env/db")
    monkeypatch.setenv("WRA_PG_DSN", "postgres://wrap/db")
    assert suggest._dsn("postgres://arg/db") == "postgres://arg/db"
    assert suggest._dsn("") == "postgres://env/db"
    monkeypatch.delenv("DATABASE_URL")
    assert suggest._dsn("") == "postgres://wrap/db"


def test_select_batch_filters_source_and_requires_vin() -> None:
    cur = _FakeCursor([[]])
    suggest._select_batch(cur, "autotrader", last_id=100, limit=50)
    sql, params = cur.executed[0]
    assert "power_hp IS NULL" in sql
    assert "COALESCE(data->>'vin', '') <> ''" in sql
    assert "AND source = %s" in sql
    assert params == (100, "autotrader", 50)

    cur2 = _FakeCursor([[]])
    suggest._select_batch(cur2, "*", last_id=0, limit=10)
    sql2, params2 = cur2.executed[0]
    assert "AND source = %s" not in sql2
    assert params2 == (0, 10)


def test_sample_from_row_uses_vpic_and_falls_back_to_card() -> None:
    payload = {
        "mark": "Ford",
        "model": "F-150",
        "year": 2019,
        "engine_type": "Gasoline",
        "displacement_cc": 3496,
    }
    info = {"hp": 400, "cc": None, "make": "Ford", "model": "F-150", "year": 2021, "fuel": "Gasoline"}
    sample = suggest._sample_from_row(payload, info)
    assert sample is not None
    assert sample["hp"] == 400
    assert sample["cc"] == 3496  # из карточки (usa_engine_cc)
    assert sample["year"] == 2021  # модельный год vPIC приоритетнее

    assert suggest._sample_from_row(payload, {"hp": None, "cc": 3496}) is None
    assert suggest._sample_from_row({"mark": "", "model": "F-150"}, {"hp": 400, "cc": 3496}) is None


def test_main_without_dsn_returns_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("WRA_PG_DSN", raising=False)
    monkeypatch.setattr(suggest, "psycopg2", None)
    monkeypatch.setattr("sys.argv", ["prog"])
    assert suggest.main() == 2


def test_main_crystallizes_vpic_observations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    rows = [
        {
            "id": 1,
            "power_hp": None,
            "data": {"mark": "Toyota", "model": "Tacoma", "year": 2022, "engine_type": "Gasoline", "vin": "3TMCZ5AN0NM000001"},
        }
    ]
    cur = _FakeCursor([rows, []])
    conn = _FakeConn(cur)
    flushed: list = []
    monkeypatch.setenv("USA_VIN_POWER", "1")
    monkeypatch.setattr(suggest, "psycopg2", _FakePsycopg2(conn))
    monkeypatch.setattr(suggest, "lookup_vin_power", lambda vin, **kw: {"hp": 278, "cc": 3456, "year": 2022})
    monkeypatch.setattr(suggest, "flush_vin_cache", lambda: flushed.append(True))
    out = tmp_path / "candidates.json"
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--dsn", "postgres://x/db", "--json-out", str(out), "--no-vin"],
    )

    assert suggest.main() == 0
    assert suggest.os.environ["USA_VIN_POWER"] == "0"  # --no-vin отключает сеть
    assert flushed == [True]
    assert conn.closed is True
    payload = json.loads(out.read_text(encoding="utf-8"))
    entries = payload["engines"]
    assert len(entries) == 1
    e = entries[0]
    assert e["make"] == "Toyota"
    assert e["model_substrings"] == ["tacoma"]
    assert e["cc"] == 3500
    assert e["hp"] == 278
    assert e["fuel"] == "gas"
    assert e["samples"] == 1
    assert "год" in payload["_comment"] or "vPIC" in payload["_comment"]
