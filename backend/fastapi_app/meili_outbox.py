"""Обработка meili_sync_outbox: PG → Meilisearch инкрементально."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from meilisearch import Client

from fastapi_app.config import Settings
from fastapi_app.tracing_ops import run_in_thread_traced

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from infrastructure.meilisearch.sync_meilisearch import row_to_document  # noqa: E402

_CAR_SELECT = """
SELECT
    c.car_id,
    c.mark,
    c.model,
    c.encar_model_group,
    c.body_type,
    c.fuel_type,
    c.transmission_type,
    c.drive_type,
    c.color,
    c.price_rub,
    c.insurance_cases,
    c.insurance_payout_krw,
    c.damaged_parts_count,
    c.year,
    c.year_month,
    c.mileage_km,
    c.power_hp,
    c.power_kw,
    c.torque_nm,
    c.displacement_cc,
    c.displacement_label,
    c.data,
    c.source,
    c.encar_listing_sold,
    c.che168_listing_sold,
    c.updated_at,
    c.created_at,
    c.dedupe_canonical_car_id
FROM cars AS c
WHERE c.car_id = ANY($1::text[])
"""


async def process_meili_outbox_batch(
    pool: asyncpg.Pool,
    meili: Client,
    settings: Settings,
    *,
    limit: int = 200,
) -> Dict[str, Any]:
    rows = await pool.fetch(
        """
        SELECT id, car_id, op
        FROM meili_sync_outbox
        WHERE processed_at IS NULL
        ORDER BY enqueued_at ASC
        LIMIT $1
        """,
        int(limit),
    )
    if not rows:
        return {"ok": True, "processed": 0, "documents": 0, "deleted": 0}

    upsert_ids: List[str] = []
    delete_ids: List[str] = []
    outbox_ids: List[int] = []
    for r in rows:
        outbox_ids.append(int(r["id"]))
        cid = str(r["car_id"])
        if str(r["op"]) == "delete":
            delete_ids.append(cid)
        else:
            upsert_ids.append(cid)

    docs: List[Dict[str, Any]] = []
    if upsert_ids:
        car_rows = await pool.fetch(_CAR_SELECT, upsert_ids)
        for cr in car_rows:
            if cr["dedupe_canonical_car_id"] is not None:
                continue
            if cr["encar_listing_sold"] or cr["che168_listing_sold"]:
                delete_ids.append(str(cr["car_id"]))
                continue
            try:
                docs.append(
                    row_to_document(dict(cr), clean_read_mode=bool(settings.clean_read_mode))
                )
            except ValueError:
                delete_ids.append(str(cr["car_id"]))

    idx = meili.index(settings.meilisearch_index)
    docs_written = 0
    deleted = 0

    if docs:

        def _add():
            return idx.add_documents(docs)

        await run_in_thread_traced("meilisearch.outbox_add", _add)
        docs_written = len(docs)

    if delete_ids:
        uniq_del = list(dict.fromkeys(delete_ids))

        def _del():
            return idx.delete_documents(uniq_del)

        await run_in_thread_traced("meilisearch.outbox_delete", _del)
        deleted = len(uniq_del)

    await pool.execute(
        """
        UPDATE meili_sync_outbox
        SET processed_at = now()
        WHERE id = ANY($1::bigint[])
        """,
        outbox_ids,
    )

    return {
        "ok": True,
        "processed": len(outbox_ids),
        "documents": docs_written,
        "deleted": deleted,
    }
