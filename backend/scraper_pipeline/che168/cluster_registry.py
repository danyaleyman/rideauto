"""Глобальные кластеры Che168 в Postgres: реестр ключей и выставление dedupe_canonical_car_id."""

from __future__ import annotations

from typing import Any, Dict, List

from catalog_dedupe import normalize_vin_for_catalog_dedupe


def che168_cluster_keys_from_listing_data(data: Dict[str, Any]) -> List[str]:
    """Ключи: API cluster_id и нормализованный VIN."""
    keys: List[str] = []
    cid = data.get("che168_listing_cluster_id")
    if cid and str(cid).strip():
        keys.append(str(cid).strip())
    vin = normalize_vin_for_catalog_dedupe(data.get("vin"))
    if vin:
        keys.append(f"vin:{vin}")
    seen: set[str] = set()
    out: List[str] = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _che168_numeric_rank(car_id: str) -> int:
    """Меньший infoid → канон (стабильно внутри одного источника)."""
    s = (car_id or "").strip()
    if not s.lower().startswith("che168-"):
        return 2**62 - 1
    try:
        return int(s.split("-", 1)[1])
    except (ValueError, IndexError):
        return 2**62 - 1


def apply_che168_cluster_registry(cur: Any, car_id: str, data: Dict[str, Any]) -> None:
    """
    Регистрирует car_id по всем ключам кластера и синхронизирует cars.dedupe_canonical_car_id
    среди участников каждого ключа (канон — минимальный che168 infoid).
    """
    if data.get("source") != "che168":
        return
    keys = che168_cluster_keys_from_listing_data(data)
    if not keys:
        return
    keys_sorted = sorted(keys, key=lambda x: (0 if x.startswith("vin:") else 1, x))

    for cluster_key in keys_sorted:
        cur.execute(
            """
            INSERT INTO che168_cluster_registry (cluster_key, car_id, updated_at)
            VALUES (%s, %s, now())
            ON CONFLICT (cluster_key, car_id) DO UPDATE SET updated_at = now()
            """,
            (cluster_key, car_id),
        )
        cur.execute(
            "SELECT car_id FROM che168_cluster_registry WHERE cluster_key = %s",
            (cluster_key,),
        )
        rows = cur.fetchall() or []
        members = [str(r[0]) for r in rows if r and r[0]]
        if len(members) < 2:
            continue
        canonical_car_id = min(members, key=_che168_numeric_rank)
        cur.execute(
            """
            UPDATE cars SET dedupe_canonical_car_id = NULL, updated_at = now()
            WHERE car_id = %s
            """,
            (canonical_car_id,),
        )
        for m in members:
            if m == canonical_car_id:
                continue
            cur.execute(
                """
                UPDATE cars SET dedupe_canonical_car_id = %s, updated_at = now()
                WHERE car_id = %s
                """,
                (canonical_car_id, m),
            )
