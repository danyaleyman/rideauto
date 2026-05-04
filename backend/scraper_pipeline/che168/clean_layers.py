"""Нормализованные clean-слои для каталога (совместимо с row_to_car_fields / clean_read)."""

from __future__ import annotations

import json
from typing import Any, Dict

CHE168_CLEAN_SCHEMA_VERSION = "che168.clean.v1"


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def build_che168_clean_layers(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    price_cny = data.get("price_cny")
    por = bool(data.get("price_on_request") is True or price_cny is None or float(price_cny or 0) <= 0)
    dealer = data.get("che168_dealer") if isinstance(data.get("che168_dealer"), dict) else {}
    imgs = data.get("images")
    if isinstance(imgs, list):
        media_json = json.dumps(imgs, ensure_ascii=False)
    else:
        media_json = _safe_str(imgs)
    disp_cc = data.get("displacement_cc")
    return {
        "clean_schema_version": CHE168_CLEAN_SCHEMA_VERSION,
        "identity_clean": {
            "car_id": _safe_str(data.get("inner_id")),
            "source": _safe_str(data.get("source") or "che168"),
            "mark": _safe_str(data.get("mark")),
            "model": _safe_str(data.get("model")),
            "mark_canonical": _safe_str(data.get("mark_canonical")),
            "model_canonical": _safe_str(data.get("model_canonical")),
            "generation": _safe_str(data.get("generation")),
            "trim_name": _safe_str(data.get("configuration")),
            "vin": _safe_str(data.get("vin")),
            "year": _safe_str(data.get("year")),
        },
        "location_clean": {
            "city": _safe_str(data.get("che168_city")),
            "province": _safe_str(data.get("che168_province")),
            "region": _safe_str(data.get("che168_region")),
            "area_id": _safe_str(data.get("che168_area_id")),
            "address_line": _safe_str(data.get("che168_address_line")),
            "cookie_area": _safe_str(data.get("che168_cookie_area")),
            "cookie_is_overseas": _safe_str(data.get("che168_cookie_is_overseas")),
        },
        "catalog_text_clean": {
            "description": _safe_str(data.get("description") or data.get("listing_text")),
            "first_registration_at": _safe_str(data.get("che168_first_registration_at")),
            "listing_published_at": _safe_str(data.get("che168_listing_published_at")),
            "price_updated_at": _safe_str(data.get("che168_price_updated_at")),
            "listing_modified_at": _safe_str(data.get("che168_listing_modified_at")),
        },
        "spec_clean": {
            "engine_type": _safe_str(data.get("engine_type")),
            "transmission_type": _safe_str(data.get("transmission_type")),
            "body_type": _safe_str(data.get("body_type")),
            "drive_type": _safe_str(data.get("drive_type")),
            "mileage_km": _safe_str(data.get("km_age")),
            "power_hp": _safe_str(data.get("power_hp")),
            "displacement_cc": _safe_str(disp_cc),
            "color": _safe_str(data.get("color")),
        },
        "pricing_clean": {
            "source_price_cny": price_cny,
            "price_on_request": por,
            "price_intent": "on_request" if por else "sale",
            "final_price_rub": data.get("my_price"),
        },
        "condition_clean": {
            "insurance_cases": data.get("insurance_cases", 0),
            "insurance_payout_krw": data.get("insurance_payout_krw", 0),
            "damaged_parts_count": data.get("damaged_parts_count", 0),
        },
        "seller_clean": {
            "seller_id": _safe_str(dealer.get("dealer_id")),
            "seller_type": "dealer",
            "is_dealer": True,
            "address": _safe_str(dealer.get("dealer_address")),
        },
        "media_clean": {
            "images_json": media_json,
            "has_images": bool(isinstance(imgs, list) and len(imgs) > 0),
        },
    }
