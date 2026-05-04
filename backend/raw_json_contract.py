from __future__ import annotations

from typing import Any, Dict, List

RAW_JSON_MIN_CONTRACT: Dict[str, List[str]] = {
    "identity": ["inner_id", "url", "mark", "model", "year"],
    "spec": ["engine_type", "transmission_type", "body_type", "km_age"],
    "pricing": ["price", "price_won", "price_intent", "price_classifier_version"],
    "quality": ["parser_schema_version", "data_quality"],
    "clean_layers": ["clean_schema_version", "identity_clean", "spec_clean", "pricing_clean"],
}

# Che168 Global: нет корейских price/price_won; год и пробег часто отсутствуют в API — не входят в минимум.
RAW_JSON_MIN_CONTRACT_CHE168: Dict[str, List[str]] = {
    "identity": ["inner_id", "source", "mark", "model"],
    # price_cny может отсутствовать (price_on_request / снятые ключи None после парсера)
    "pricing": ["price_on_request", "parser_schema_version", "data_quality"],
    "clean_layers": [
        "clean_schema_version",
        "identity_clean",
        "spec_clean",
        "pricing_clean",
        "location_clean",
        "catalog_text_clean",
    ],
}


def _raw_json_contract_for(data: Dict[str, Any]) -> Dict[str, List[str]]:
    if isinstance(data, dict) and str(data.get("source") or "").strip().lower() == "che168":
        return RAW_JSON_MIN_CONTRACT_CHE168
    return RAW_JSON_MIN_CONTRACT


def validate_raw_json_min_contract(data: Dict[str, Any]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    contract = _raw_json_contract_for(data if isinstance(data, dict) else {})
    if not isinstance(data, dict):
        return {k: list(v) for k, v in contract.items()}
    for group, fields in contract.items():
        missing: List[str] = []
        for f in fields:
            v = data.get(f)
            if v is None:
                missing.append(f)
                continue
            if isinstance(v, str) and not v.strip():
                missing.append(f)
                continue
            if isinstance(v, dict) and not v:
                missing.append(f)
                continue
        if missing:
            out[group] = missing
    return out

