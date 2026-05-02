from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_sync_module():
    root = Path(__file__).resolve().parents[2]
    p = root / "infrastructure" / "meilisearch" / "sync_meilisearch.py"
    spec = importlib.util.spec_from_file_location("sync_meilisearch", str(p))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_row_to_document_prefers_clean_fields_in_clean_read_mode():
    mod = _load_sync_module()
    row = {
        "pg_id": 1,
        "car_id": "encar-1",
        "mark": "legacy-mark",
        "model": "legacy-model",
        "fuel_type": "legacy-fuel",
        "price_rub": 1000,
        "generation": "",
        "trim_name": "",
        "transmission_type": "",
        "drive_type": "",
        "color": "",
        "body_type": "",
        "year": None,
        "year_month": None,
        "mileage_km": None,
        "power_hp": None,
        "power_kw": None,
        "torque_nm": None,
        "displacement_cc": None,
        "displacement_label": None,
        "source": "encar",
        "updated_at": None,
        "created_at": None,
        "data": {
            "identity_clean": {"mark": "BMW", "model": "X5", "generation": "G05"},
            "spec_clean": {"engine_type": "Бензин"},
            "pricing_clean": {"final_price_rub": 2000},
        },
    }
    doc = mod.row_to_document(row, clean_read_mode=True)
    assert doc["brand"] == "BMW"
    assert doc["model"] == "X5"
    assert doc["model_group"] == "X5"
    assert doc["model_cluster"] == "X5"
    assert doc["generation"] == "G05"
    assert doc["fuel"] == "Бензин"
    assert doc["price"] == 2000.0


def test_row_to_document_model_group_prefers_encar_column_over_heuristic():
    mod = _load_sync_module()
    row = {
        "pg_id": 2,
        "car_id": "encar-9",
        "mark": "Kia",
        "model": "EV6 (Long Range)",
        "encar_model_group": "The New EV6",
        "fuel_type": "",
        "price_rub": None,
        "generation": "",
        "trim_name": "",
        "transmission_type": "",
        "drive_type": "",
        "color": "",
        "body_type": "",
        "year": None,
        "year_month": None,
        "mileage_km": None,
        "power_hp": None,
        "power_kw": None,
        "torque_nm": None,
        "displacement_cc": None,
        "displacement_label": None,
        "source": "encar",
        "updated_at": None,
        "created_at": None,
        "data": {},
    }
    doc = mod.row_to_document(row, clean_read_mode=False)
    assert doc["model_group"] == "The New EV6"
    assert doc["model_cluster"]


def test_row_to_document_model_group_falls_back_to_json_modelGroupName_without_column():
    mod = _load_sync_module()
    row = {
        "pg_id": 3,
        "car_id": "encar-10",
        "mark": "Kia",
        "model": "EV6 (XR)",
        "encar_model_group": None,
        "fuel_type": "",
        "price_rub": None,
        "generation": "",
        "trim_name": "",
        "transmission_type": "",
        "drive_type": "",
        "color": "",
        "body_type": "",
        "year": None,
        "year_month": None,
        "mileage_km": None,
        "power_hp": None,
        "power_kw": None,
        "torque_nm": None,
        "displacement_cc": None,
        "displacement_label": None,
        "source": "encar",
        "updated_at": None,
        "created_at": None,
        "data": {"modelGroupName": "EV6 MY2024"},
    }
    doc = mod.row_to_document(row, clean_read_mode=False)
    assert doc["model_group"] == "EV6 MY2024"
    assert doc["model_cluster"]


def test_row_to_document_model_cluster_maps_avante_ad():
    mod = _load_sync_module()
    row = {
        "pg_id": 4,
        "car_id": "encar-avante",
        "mark": "Hyundai",
        "model": "Avante AD 1.6",
        "encar_model_group": "Avante AD",
        "fuel_type": "",
        "price_rub": None,
        "generation": "",
        "trim_name": "",
        "transmission_type": "",
        "drive_type": "",
        "color": "",
        "body_type": "",
        "year": None,
        "year_month": None,
        "mileage_km": None,
        "power_hp": None,
        "power_kw": None,
        "torque_nm": None,
        "displacement_cc": None,
        "displacement_label": None,
        "source": "encar",
        "updated_at": None,
        "created_at": None,
        "data": {},
    }
    doc = mod.row_to_document(row, clean_read_mode=False)
    assert doc["model_group"] == "Avante AD"
    assert doc["model_cluster"] == "Avante"

