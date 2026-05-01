"""Parser: нормализация ответов API через EncarFullParser (CPU-bound → executor)."""

from __future__ import annotations

import asyncio
import logging
import time
from functools import partial
from typing import Any, Dict, Optional

from parser_full import EncarFullParser

log = logging.getLogger(__name__)
RAW_ENVELOPE_VERSION = "encar.raw.v1"


def _shape_hash(payload: Any) -> str:
    import hashlib

    if not isinstance(payload, dict):
        return ""
    keys = sorted(str(k) for k in payload.keys())
    if not keys:
        return ""
    return hashlib.sha1("|".join(keys).encode("utf-8")).hexdigest()[:12]


def _build_raw_envelope(
    *,
    parser_schema_version: str,
    item: Optional[Dict[str, Any]],
    detail: Optional[Dict[str, Any]],
    diagnosis: Optional[Dict[str, Any]],
    record: Optional[Dict[str, Any]],
    inspection: Optional[Dict[str, Any]],
    sellingpoint: Optional[Dict[str, Any]],
    user_info: Optional[Dict[str, Any]],
    source_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    sources: Dict[str, Any] = {
        "list_item": item if isinstance(item, dict) else None,
        "detail": detail if isinstance(detail, dict) else None,
        "diagnosis": diagnosis if isinstance(diagnosis, dict) else None,
        "record": record if isinstance(record, dict) else None,
        "inspection": inspection if isinstance(inspection, dict) else None,
        "sellingpoint": sellingpoint if isinstance(sellingpoint, dict) else None,
        "user": user_info if isinstance(user_info, dict) else None,
    }
    present = [k for k, v in sources.items() if isinstance(v, dict)]
    expected = list(sources.keys())
    missing = [k for k in expected if k not in present]
    return {
        "raw_schema_version": RAW_ENVELOPE_VERSION,
        "parser_schema_version": parser_schema_version,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": sources,
        "integrity": {
            "expected_sources": expected,
            "present_sources": present,
            "missing_sources": missing,
            "coverage_pct": round((len(present) / len(expected)) * 100.0, 2) if expected else 0.0,
            "shape_hashes": {k: _shape_hash(v) for k, v in sources.items()},
        },
        "source_meta": source_meta or {},
    }

def parse_one_car_sync(
    parser: EncarFullParser,
    car_id: str,
    item: dict,
    detail: Optional[dict],
    diagnosis: Optional[dict],
    record: Optional[dict],
    inspection: Optional[dict],
    sellingpoint: Optional[dict],
    user_info: Optional[dict],
    source_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[dict]:
    started = time.perf_counter()
    try:
        inspection_structured = parser.parse_inspection(inspection, diagnosis) if (inspection or diagnosis) else {}
        photos = None
        if detail:
            photos = detail.get("photos") or []
        normalized = parser.normalize_car(
            car_id,
            item,
            detail,
            photos,
            diagnosis,
            inspection,
            sellingpoint,
            record,
            user_info,
            inspection_structured=inspection_structured,
        )
        normalized["id"] = car_id
        normalized["data"]["id"] = str(car_id)
        parser_schema_version = str((normalized.get("data") or {}).get("parser_schema_version") or "")
        raw_envelope = _build_raw_envelope(
            parser_schema_version=parser_schema_version,
            item=item,
            detail=detail,
            diagnosis=diagnosis,
            record=record,
            inspection=inspection,
            sellingpoint=sellingpoint,
            user_info=user_info,
            source_meta=source_meta,
        )
        normalized["data"]["raw_envelope"] = raw_envelope
        quality = ((normalized.get("data") or {}).get("data_quality") or {})
        if isinstance(quality, dict):
            coverage = float(raw_envelope["integrity"]["coverage_pct"])
            quality["raw_coverage_pct"] = coverage
            missing_required = quality.get("missing_required_fields") or []
            miss_penalty = min(40, len(missing_required) * 8) if isinstance(missing_required, list) else 0
            source_penalty = int(max(0.0, 100.0 - coverage) * 0.5)
            quality["raw_quality_score"] = max(0, int(round(100 - miss_penalty - source_penalty)))
            if raw_envelope["integrity"]["missing_sources"]:
                reasons = quality.setdefault("reasons", [])
                if isinstance(reasons, list) and "raw_sources_missing" not in reasons:
                    reasons.append("raw_sources_missing")
        # Saver writes `cars.raw` from this payload when store_raw_responses=true.
        # Keep full raw envelope for replay/reprocessing.
        normalized["_raw"] = raw_envelope
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        missing = quality.get("missing_required_fields") or []
        if missing:
            log.warning("normalized with missing required fields car_id=%s missing=%s elapsed_ms=%s", car_id, ",".join(missing), elapsed_ms)
        else:
            log.debug("normalized car_id=%s elapsed_ms=%s", car_id, elapsed_ms)
        return normalized
    except Exception:
        log.exception("normalize failed for car_id=%s", car_id)
        return None


async def parse_one_car_async(
    parser: EncarFullParser,
    car_id: str,
    item: dict,
    detail: Optional[dict],
    diagnosis: Optional[dict],
    record: Optional[dict],
    inspection: Optional[dict],
    sellingpoint: Optional[dict],
    user_info: Optional[dict],
    source_meta: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[dict]:
    loop = asyncio.get_running_loop()
    fn = partial(
        parse_one_car_sync,
        parser,
        car_id,
        item,
        detail,
        diagnosis,
        record,
        inspection,
        sellingpoint,
        user_info,
        source_meta,
    )
    return await loop.run_in_executor(None, fn)
