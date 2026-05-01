from __future__ import annotations

from typing import Any, Dict, List

RAW_JSON_MIN_CONTRACT: Dict[str, List[str]] = {
    "identity": ["inner_id", "url", "mark", "model", "year"],
    "spec": ["engine_type", "transmission_type", "body_type", "km_age"],
    "pricing": ["price", "price_won", "price_intent", "price_classifier_version"],
    "quality": ["parser_schema_version", "data_quality"],
    "clean_layers": ["clean_schema_version", "identity_clean", "spec_clean", "pricing_clean"],
}


def validate_raw_json_min_contract(data: Dict[str, Any]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    if not isinstance(data, dict):
        return {k: list(v) for k, v in RAW_JSON_MIN_CONTRACT.items()}
    for group, fields in RAW_JSON_MIN_CONTRACT.items():
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

