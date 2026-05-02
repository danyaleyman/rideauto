"""Регрессия: слойность hp_catalog (observed / LLM) и фильтр confidence."""
from __future__ import annotations

import sqlite3
import sys
import types
from pathlib import Path

import hp_catalog_store
import pytest

import power_from_external as m


def _stub_engine_hp_resolver_resolve_none() -> None:
    stub = types.ModuleType("engine_hp_resolver")

    def resolve_engine_hp(car_data: dict, record_source: bool = False) -> None:
        return None

    stub.resolve_engine_hp = resolve_engine_hp  # type: ignore[attr-defined]
    sys.modules["engine_hp_resolver"] = stub


def _insert_row(sqlite_path: Path, **kwargs: object) -> None:
    conn = sqlite3.connect(str(sqlite_path))
    try:
        hp_catalog_store.ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO hp_catalog (
              manufacturer, model, version, engine_type, displacement_cc, drive, year_month,
              power_hp, power_kw,
              norm_manufacturer, norm_model, norm_version, norm_engine_type,
              llm_status, llm_reason, llm_attempts, llm_confidence, source,
              updated_at
            ) VALUES (
              :manufacturer, :model, :version, :engine_type, :displacement_cc, '', :year_month,
              :power_hp, :power_kw,
              :nm, :nmd, :nv, :net,
              :llm_status, '', 1, :llm_confidence, :source,
              strftime('%Y-%m-%dT%H:%M:%fZ','now')
            )
            """,
            kwargs,
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _clear_engine_hp_stub():
    yield
    sys.modules.pop("engine_hp_resolver", None)


def test_hp_catalog_observed_beats_fake_engine_map(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "hc.db"
    monkeypatch.setattr(m, "HP_CATALOG_DB_PATH", db_path)
    m.invalidate_hp_catalog_cache()

    nm = hp_catalog_store.normalize_key_part("Hyundai")
    nmd = hp_catalog_store.normalize_key_part("Avante")
    nv = hp_catalog_store.normalize_key_part("Comfort")
    net = hp_catalog_store.normalize_key_part("Gasoline")

    row = dict(
        manufacturer="Hyundai",
        model="Avante",
        version="Comfort",
        engine_type="Gasoline",
        displacement_cc=2000,
        year_month="202001",
        power_hp=173,
        power_kw=127.5,
        nm=nm,
        nmd=nmd,
        nv=nv,
        net=net,
        llm_status="done",
        llm_confidence=1.0,
        source="postgres",
    )
    _insert_row(db_path, **row)

    def resolve_engine_hp(car_data: dict, record_source: bool = False) -> int:
        return 99

    stub_mod = types.ModuleType("engine_hp_resolver")
    stub_mod.resolve_engine_hp = resolve_engine_hp  # type: ignore[attr-defined]
    sys.modules["engine_hp_resolver"] = stub_mod

    car_inner = dict(
        mark="Hyundai",
        model="Avante",
        gradeName="Comfort",
        engine_type="Gasoline",
        displacement="2000",
        yearMonth="2020-01",
    )
    assert m.get_power_for_car(car_inner, record_source=False) == 173


def test_hp_catalog_llm_requires_confidence_after_threshold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "hc2.db"
    monkeypatch.setattr(m, "HP_CATALOG_DB_PATH", db_path)
    monkeypatch.setenv("HP_LLM_MIN_CONFIDENCE", "0.71")
    m.invalidate_hp_catalog_cache()

    nm = hp_catalog_store.normalize_key_part("Kia")
    nmd = hp_catalog_store.normalize_key_part("K5")
    nv = hp_catalog_store.normalize_key_part("")
    net = hp_catalog_store.normalize_key_part("Gasoline")

    for conf, hp_val in ((0.50, 180), (0.80, 195)):
        _stub_engine_hp_resolver_resolve_none()
        # Чистый файл на каждый под-случай
        if db_path.is_file():
            db_path.unlink()
        m.invalidate_hp_catalog_cache()
        row = dict(
            manufacturer="Kia",
            model="K5",
            version="",
            engine_type="Gasoline",
            displacement_cc=1600,
            year_month="202101",
            power_hp=hp_val,
            power_kw=float(hp_catalog_store.hp_to_kw(hp_val)),
            nm=nm,
            nmd=nmd,
            nv=nv,
            net=net,
            llm_status="done",
            llm_confidence=conf,
            source="catalog",
        )
        _insert_row(db_path, **row)
        obs, llm_ok = m._rebuild_hp_catalog_indices()
        car_inner = dict(
            mark="Kia",
            model="K5",
            engine_type="Gasoline",
            displacement="1600",
            yearMonth="2021-01",
        )
        expected = None if conf < 0.71 else hp_val
        assert m._scan_index(llm_ok, car_inner) == expected
        assert m._scan_index(obs, car_inner) is None
