from __future__ import annotations

from typing import Any, Dict


CLEAN_SCHEMA_VERSION = "encar.clean.v1"


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def build_clean_layers(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "clean_schema_version": CLEAN_SCHEMA_VERSION,
            "identity_clean": {},
            "spec_clean": {},
            "pricing_clean": {},
            "condition_clean": {},
            "seller_clean": {},
            "media_clean": {},
        }
    return {
        "clean_schema_version": CLEAN_SCHEMA_VERSION,
        "identity_clean": {
            "car_id": _safe_str(data.get("inner_id")),
            "source": _safe_str(data.get("source") or "encar"),
            "url": _safe_str(data.get("url")),
            "mark": _safe_str(data.get("mark")),
            "model": _safe_str(data.get("model")),
            "generation": _safe_str(data.get("generation")),
            "trim_name": _safe_str(data.get("gradeName")),
            "model_group_encar": _safe_str(data.get("modelGroupName")),
            "vin": _safe_str(data.get("vin")),
            "year": _safe_str(data.get("year")),
        },
        "spec_clean": {
            "engine_type": _safe_str(data.get("engine_type")),
            "transmission_type": _safe_str(data.get("transmission_type")),
            "body_type": _safe_str(data.get("body_type")),
            "drive_type": _safe_str(data.get("drive_type") or data.get("prep_drive_type")),
            "mileage_km": _safe_str(data.get("km_age")),
            "power_hp": _safe_str(data.get("power")),
            "displacement_cc": _safe_str(data.get("displacement")),
            "color": _safe_str(data.get("color")),
        },
        "pricing_clean": {
            "source_price_mw": _safe_str(data.get("price")),
            "source_price_won": data.get("price_won"),
            "source_price_text": _safe_str(data.get("price_text")),
            "price_intent": _safe_str(data.get("price_intent")),
            "price_signals": _safe_str(data.get("price_signals")),
            "price_on_request": bool(data.get("price_on_request") is True),
            "reserved_placeholder": bool(data.get("encar_listing_reserved") is True),
            "final_price_rub": data.get("my_price"),
        },
        "condition_clean": {
            "insurance_cases": data.get("insurance_cases", 0),
            "insurance_payout_krw": data.get("insurance_payout_krw", 0),
            "damaged_parts_count": data.get("damaged_parts_count", 0),
            "inspection_available": bool((data.get("extra") or {}).get("inspection")),
            "diagnosis_available": bool((data.get("extra") or {}).get("diagnosis")),
        },
        "seller_clean": {
            "seller_id": _safe_str(data.get("seller")),
            "seller_type": _safe_str(data.get("seller_type")),
            "is_dealer": bool(data.get("is_dealer") is True),
            "salon_id": _safe_str(data.get("salon_id")),
            "address": _safe_str(data.get("address")),
        },
        "media_clean": {
            "images_json": _safe_str(data.get("images")),
            "images_meta_json": _safe_str(data.get("h_images")),
            "has_images": bool(_safe_str(data.get("images"))),
        },
    }


def build_catalog_clean_layers(data: Dict[str, Any]) -> Dict[str, Any]:
    """Единая точка входа: Encar (`encar.clean.v*`) или China (`che168.clean.v*`)."""
    if not isinstance(data, dict):
        return build_clean_layers(data)
    if str(data.get("source") or "").strip().lower() == "che168":
        from scraper_pipeline.che168.clean_layers import build_che168_clean_layers

        return build_che168_clean_layers(data)
    return build_clean_layers(data)
