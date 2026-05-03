"""Сравнение read model при use_clean=True vs False (для rollout блока D)."""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

# Поля read model, где расхождение обычно не «баг rollout», а разные строки локализации
# (legacy через локализатор / RU, clean — сырой KO из Encar в spec_clean).
SEMANTIC_COMPARE_KEYS: FrozenSet[str] = frozenset(
    {
        "price_rub",
        "price_on_request",
        "reserved_placeholder",
        "pricing_tier",
        "customs_included",
        "insurance_cases",
        "damaged_parts_count",
        "drive_type",
        "power_hp",
    }
)


def diff_read_model_fields(
    legacy: Mapping[str, Any],
    clean: Mapping[str, Any],
    *,
    keys_only: Optional[FrozenSet[str]] = None,
) -> List[str]:
    """Список ключей, где значения различаются (строгое сравнение)."""
    if keys_only is not None:
        keys = set(keys_only)
    else:
        keys = set(legacy.keys()) | set(clean.keys())
    out: List[str] = []
    for k in sorted(keys):
        if legacy.get(k) != clean.get(k):
            out.append(k)
    return out


def aggregate_dual_run_stats(
    rows: List[Tuple[str, Dict[str, Any], Dict[str, Any]]],
    *,
    semantic: bool = False,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    rows: (car_id, legacy_rm, clean_rm)
    Возвращает stats (счётчики) и sample (до N примеров с расхождениями).
    """
    keyset = SEMANTIC_COMPARE_KEYS if semantic else None
    stats: Dict[str, Any] = {
        "checked": 0,
        "rows_with_any_diff": 0,
        "by_field": {},
        "compare_mode": "semantic" if semantic else "full",
    }
    sample: List[Dict[str, Any]] = []
    max_sample = 25

    for car_id, legacy, clean in rows:
        stats["checked"] += 1
        fields = diff_read_model_fields(legacy, clean, keys_only=keyset)
        if not fields:
            continue
        stats["rows_with_any_diff"] += 1
        for f in fields:
            stats["by_field"][f] = int(stats["by_field"].get(f, 0)) + 1
        if len(sample) < max_sample:
            sample.append(
                {
                    "car_id": car_id,
                    "fields": fields,
                    "legacy": dict(legacy),
                    "clean": dict(clean),
                }
            )

    n = max(1, int(stats["checked"]))
    stats["pct_rows_with_any_diff"] = round(100.0 * float(stats["rows_with_any_diff"]) / n, 2)
    stats["pct_by_field"] = {k: round(100.0 * float(v) / n, 2) for k, v in stats["by_field"].items()}
    return stats, sample


def dual_run_should_fail(stats: Dict[str, Any], *, max_row_diff_pct: float) -> Tuple[bool, str]:
    """True если порог превышен и прогон считаем проваленным."""
    if max_row_diff_pct < 0:
        return False, ""
    pct = float(stats.get("pct_rows_with_any_diff") or 0.0)
    if pct > max_row_diff_pct + 1e-9:
        return True, f"pct_rows_with_any_diff={pct}% > max_row_diff_pct={max_row_diff_pct}%"
    return False, ""
