#!/usr/bin/env python3
"""
Full or incremental sync: PostgreSQL `cars` → Meilisearch index `cars`.

Field mapping (Meilisearch document):
  catalog_dedupe_key ← VIN (нормализованный, ≥11) или source:inner_id или id:car_id (см. `backend/catalog_dedupe.py`);
                      при `distinctAttribute` в index settings — не более одного хита на ключ в поиске.
  brand         ← cars.mark
  model         ← cars.model
  model_cluster ← линейка (склейка вариантов; data/model_cluster_rules.json + эвристика)
  model_group   ← cars.encar_model_group (Encar) или суффикс model без «(…)»
  price       ← cars.price_rub
  year        ← cars.year
  color       ← cars.color
  body_type   ← cars.body_type
  mileage     ← cars.mileage_km
  fuel        ← cars.fuel_type  (Encar `engine_type`, UI «топливо»)
  power_hp    ← cars.power_hp
  power_kw    ← cars.power_kw
  torque_nm   ← cars.torque_nm
  displacement_cc ← cars.displacement_cc
  displacement_label ← cars.displacement_label

Primary key: document `id` = cars.car_id (string).

Usage:
  python sync_meilisearch.py \\
    --pg-dsn "postgresql://user:pass@localhost:5432/wra" \\
    --meili-url "http://127.0.0.1:7700" \\
    --meili-key "$MEILI_MASTER_KEY" \\
    --settings ./index_settings.json

Optional:
  --batch-size 2000
  --index-name cars
  --live-index-name cars
  --swap-into-live   (sync into --index-name as build/staging, then swap with live; preflight still blocks writes on failure)
  --settings-only
  --recreate-index
  --since 2025-01-01T00:00:00+00:00
  --no-wait-batches

Requires:
  pip install meilisearch psycopg2-binary
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

try:
    from meilisearch import Client
    from meilisearch.errors import MeilisearchApiError
except ImportError:
    print("Install meilisearch: pip install meilisearch", file=sys.stderr)
    sys.exit(1)


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _meili_repo_and_backend() -> tuple[Path, Path]:
    """Monorepo: repo/infrastructure/meilisearch → (repo, repo/backend). Docker WORKDIR=/app → (/app, /app)."""
    repo = Path(__file__).resolve().parents[2]
    backend = repo / "backend"
    if backend.is_dir():
        return repo, backend
    return repo, repo


_REPO_ROOT_MEILI, _BACKEND_MEILI = _meili_repo_and_backend()
if str(_BACKEND_MEILI) not in sys.path:
    sys.path.insert(0, str(_BACKEND_MEILI))
try:
    from catalog_dedupe import catalog_dedupe_key as _catalog_dedupe_key  # noqa: E402
    from catalog_model_cluster import compute_model_cluster as _compute_model_cluster  # noqa: E402
except ImportError:  # tests / упаковка без backend в PYTHONPATH

    def _compute_model_cluster(brand: str, model_group: str, *, rules_path: Optional[str] = None) -> str:
        return (model_group or "").strip()

    def _catalog_dedupe_key(car_id: str, source: Optional[str], listing_root: Dict[str, Any]) -> str:
        cid = str(car_id or "").strip()
        return f"id:{cid}" if cid else "id:unknown"


_MEILI_INVALID_KEY_HINT = (
    "Ключ API должен совпадать с MEILI_MASTER_KEY экземпляра Meilisearch "
    "(как в .env / docker-compose у сервиса meilisearch).\n"
    "  Показать ключ из контейнера: "
    "docker compose exec -T meilisearch sh -c 'printf %s \"$MEILI_MASTER_KEY\"'\n"
    "  Затем: export MEILI_MASTER_KEY='…' и снова sync, либо --meili-key '…'.\n"
    "Если Meili запущен без master key — unset MEILI_MASTER_KEY и не передавайте --meili-key."
)


def _optional_since(raw: Optional[str]) -> Optional[datetime]:
    if raw is None or not str(raw).strip():
        return None
    s = str(raw).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"invalid --since datetime: {raw!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _fmt_ts_for_meili(dt: Optional[Any]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        d = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return d.isoformat().replace("+00:00", "Z")
    return str(dt)


_MODEL_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _parse_int_km(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        if isinstance(v, str):
            s = v.strip().replace("\u00a0", " ").replace(" ", "").replace(",", "").replace("'", "")
            if not s:
                return None
            return int(float(s))
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _year_for_document(row: Dict[str, Any]) -> Optional[int]:
    """Год в индексе: колонка cars.year или из year_month (YYYYMM), иначе None."""
    if row.get("year") is not None and str(row.get("year")).strip() != "":
        try:
            y = int(row["year"])
            if y > 0:
                return y
        except (TypeError, ValueError):
            pass
    ym = row.get("year_month")
    if ym is not None and str(ym).strip() != "":
        try:
            iv = int(ym)
            if iv >= 190001:
                return iv // 100
        except (TypeError, ValueError):
            pass
    return None


def _mileage_from_row(row: Dict[str, Any]) -> Optional[int]:
    km = _parse_int_km(row.get("mileage_km"))
    if km is not None:
        return km
    raw = row.get("data")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None
    if isinstance(raw, dict):
        return _parse_int_km(raw.get("km_age"))
    return None


def _model_group(model: str) -> str:
    s = (model or "").strip()
    if not s:
        return s
    prev = s
    while True:
        nxt = _MODEL_TRAILING_PAREN_RE.sub("", prev).strip()
        if not nxt or nxt == prev:
            break
        prev = nxt
    return prev or s


def _listing_json_root(row: Dict[str, Any]) -> Dict[str, Any]:
    """Корень JSON из `cars.data`: часто `{ "data": { …поля каталога… } }`."""
    raw = row.get("data")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    inner = raw.get("data")
    if isinstance(inner, dict) and (
        isinstance(inner.get("pricing_clean"), dict)
        or isinstance(inner.get("identity_clean"), dict)
        or isinstance(inner.get("mark"), str)
        or isinstance(inner.get("pricing_tier"), str)
    ):
        return inner
    return raw


def _encar_model_group_for_document(row: Dict[str, Any]) -> str:
    mg = str(row.get("encar_model_group") or "").strip()
    if mg:
        return mg
    lj = _listing_json_root(row)
    if not isinstance(lj, dict):
        return ""
    ic = lj.get("identity_clean")
    if isinstance(ic, dict):
        s = str(ic.get("model_group_encar") or "").strip()
        if s:
            return s
    return str(lj.get("modelGroupName") or "").strip()


def _clean_block(row: Dict[str, Any], key: str) -> Dict[str, Any]:
    raw = _listing_json_root(row)
    if not isinstance(raw, dict):
        return {}
    b = raw.get(key)
    return b if isinstance(b, dict) else {}


def row_to_document(row: Dict[str, Any], *, clean_read_mode: bool = False) -> Dict[str, Any]:
    car_id = row.get("car_id")
    if not car_id:
        raise ValueError("row missing car_id")

    identity = _clean_block(row, "identity_clean") if clean_read_mode else {}
    spec = _clean_block(row, "spec_clean") if clean_read_mode else {}
    pricing = _clean_block(row, "pricing_clean") if clean_read_mode else {}
    base_model = str(identity.get("model") or row.get("model") or "").strip()
    mg_doc = _encar_model_group_for_document(row)
    mg_final = mg_doc if mg_doc else _model_group(base_model)
    brand_s = str(identity.get("mark") or row.get("mark") or "").strip()
    mc = _compute_model_cluster(brand_s, mg_final)
    doc: Dict[str, Any] = {
        "id": str(car_id),
        "pg_id": int(row["pg_id"]),
        "car_id": str(car_id),
        "brand": brand_s,
        "model": base_model,
        "model_cluster": mc if mc else mg_final,
        "model_group": mg_final,
        "fuel": str(spec.get("engine_type") or row.get("fuel_type") or "").strip(),
        "color": str(spec.get("color") or row.get("color") or "").strip(),
        "body_type": str(spec.get("body_type") or row.get("body_type") or "").strip(),
        "generation": str(identity.get("generation") or row.get("generation") or "").strip(),
        "trim": str(identity.get("trim_name") or row.get("trim_name") or "").strip(),
        "transmission": str(spec.get("transmission_type") or row.get("transmission_type") or "").strip(),
        "drive_type": str(spec.get("drive_type") or row.get("drive_type") or "").strip(),
    }

    src = row.get("source")
    if src is not None and str(src).strip():
        doc["source"] = str(src).strip()

    price_v = pricing.get("final_price_rub") if clean_read_mode else None
    if price_v is None:
        price_v = row.get("price_rub")
    if price_v is not None:
        doc["price"] = float(price_v)
    if row.get("insurance_cases") is not None:
        doc["insurance_cases"] = int(row["insurance_cases"])
    if row.get("insurance_payout_krw") is not None:
        doc["insurance_payout_krw"] = int(row["insurance_payout_krw"])
    if row.get("damaged_parts_count") is not None:
        doc["damaged_parts_count"] = int(row["damaged_parts_count"])
    if row.get("encar_listing_sold") is not None:
        doc["encar_listing_sold"] = bool(row.get("encar_listing_sold"))
    if row.get("dongchedi_listing_sold") is not None:
        doc["dongchedi_listing_sold"] = bool(row.get("dongchedi_listing_sold"))
    yr = _year_for_document(row)
    if yr is not None:
        doc["year"] = int(yr)
    m_km = _mileage_from_row(row)
    if m_km is not None:
        doc["mileage"] = int(m_km)
    if row.get("power_hp") is not None:
        doc["power_hp"] = int(row["power_hp"])
    if row.get("power_kw") is not None:
        doc["power_kw"] = int(row["power_kw"])
    if row.get("torque_nm") is not None:
        doc["torque_nm"] = int(row["torque_nm"])
    if row.get("displacement_cc") is not None:
        doc["displacement_cc"] = int(row["displacement_cc"])
    if row.get("displacement_label") is not None and str(row.get("displacement_label")).strip():
        doc["displacement_label"] = str(row.get("displacement_label")).strip()
    if row.get("year_month") is not None:
        doc["year_month"] = int(row["year_month"])

    lj = _listing_json_root(row)
    tier = lj.get("pricing_tier") if isinstance(lj, dict) else None
    pc = lj.get("pricing_clean") if isinstance(lj.get("pricing_clean"), dict) else {}
    if not isinstance(tier, str):
        tier = (pc.get("pricing_tier") if isinstance(pc.get("pricing_tier"), str) else None) or None
    if isinstance(tier, str) and tier.strip():
        doc["pricing_tier"] = tier.strip()
    ci = pc.get("customs_included") if isinstance(pc.get("customs_included"), bool) else None
    if ci is None and isinstance(tier, str):
        if tier == "full_customs":
            ci = True
        elif tier in ("korea_land_only", "price_on_request"):
            ci = False
    if isinstance(ci, bool):
        doc["customs_included"] = ci

    updated = _fmt_ts_for_meili(row.get("updated_at"))
    if updated:
        doc["updated_at"] = updated

    listed = _fmt_ts_for_meili(row.get("created_at"))
    if listed:
        doc["catalog_created_at"] = listed

    lj_dedupe = _listing_json_root(row)
    doc["catalog_dedupe_key"] = _catalog_dedupe_key(
        str(car_id),
        str(row.get("source") or "") if row.get("source") is not None else None,
        lj_dedupe if isinstance(lj_dedupe, dict) else {},
    )

    return doc


def load_settings(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("index settings JSON must be an object")
    return data


def ensure_index(client: Client, uid: str, *, recreate: bool) -> None:
    if recreate:
        try:
            task = client.delete_index(uid)
            client.wait_for_task(task.task_uid, timeout_in_ms=600_000)
        except MeilisearchApiError:
            pass
    try:
        client.get_index(uid)
    except MeilisearchApiError:
        task = client.create_index(uid, {"primaryKey": "id"})
        client.wait_for_task(task.task_uid, timeout_in_ms=600_000)


def apply_settings(client: Client, uid: str, settings: Dict[str, Any]) -> None:
    index = client.index(uid)
    task = index.update_settings(settings)
    client.wait_for_task(task.task_uid, timeout_in_ms=600_000)


def iter_car_rows(
    dsn: str,
    *,
    since: Optional[datetime],
    batch_size: int,
):
    conn = psycopg2.connect(dsn)
    try:
        q = """
            SELECT
                c.id AS pg_id,
                c.car_id,
                c.mark,
                c.model,
                c.generation,
                c.trim_name,
                c.encar_model_group,
                c.fuel_type,
                c.body_type,
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
                c.dongchedi_listing_sold,
                c.updated_at,
                c.created_at
            FROM cars AS c
            WHERE (c.dedupe_canonical_car_id IS NULL)
              AND (%s::timestamptz IS NULL OR c.updated_at >= %s::timestamptz)
            ORDER BY c.id ASC
        """
        itersize = max(256, min(batch_size, 5000))
        with conn.cursor(name="wra_meili_sync", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.itersize = itersize
            cur.execute(q, (since, since))
            for row in cur:
                yield dict(row)
    finally:
        conn.close()


def push_batches(
    client: Client,
    uid: str,
    dsn: str,
    *,
    since: Optional[datetime],
    batch_size: int,
    wait_each_batch: bool,
    clean_read_mode: bool,
) -> int:
    index = client.index(uid)
    total = 0
    batch: List[Dict[str, Any]] = []

    for row in iter_car_rows(dsn, since=since, batch_size=batch_size):
        try:
            batch.append(row_to_document(row, clean_read_mode=clean_read_mode))
        except ValueError:
            continue
        if len(batch) >= batch_size:
            task = index.add_documents(batch)
            if wait_each_batch:
                client.wait_for_task(task.task_uid, timeout_in_ms=1_800_000)
            total += len(batch)
            batch.clear()

    if batch:
        task = index.add_documents(batch)
        if wait_each_batch:
            client.wait_for_task(task.task_uid, timeout_in_ms=1_800_000)
        total += len(batch)

    return total


def main() -> None:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Sync PostgreSQL cars → Meilisearch")
    parser.add_argument("--pg-dsn", default="", help="PostgreSQL connection URI")
    parser.add_argument("--meili-url", default="http://127.0.0.1:7700", help="Meilisearch server URL")
    parser.add_argument("--meili-key", default="", help="Meilisearch API key (Bearer)")
    parser.add_argument(
        "--index-name",
        default="cars",
        help="Meilisearch index UID (documents target; use another UID + --swap-into-live for blue/green)",
    )
    parser.add_argument(
        "--live-index-name",
        default=os.environ.get("WRA_MEILI_LIVE_INDEX", "cars").strip() or "cars",
        help="Production UID when using --swap-into-live (must differ from --index-name)",
    )
    parser.add_argument(
        "--swap-into-live",
        action="store_true",
        help="After sync, atomically swap live index with build index (Meilisearch swap-indexes API)",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=here / "index_settings.json",
        help="PATCH body for /indexes/{uid}/settings",
    )
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--settings-only", action="store_true", help="Apply settings only (no documents)")
    parser.add_argument("--recreate-index", action="store_true", help="Delete index UID if it exists, then recreate")
    parser.add_argument("--since", default=None, help="Only rows with updated_at >= this ISO-8601 instant")
    parser.add_argument(
        "--no-wait-batches",
        action="store_true",
        help="Do not wait for Meilisearch between batches (faster; poll tasks in /tasks)",
    )
    parser.add_argument(
        "--clean-read-mode",
        action="store_true",
        default=str(os.environ.get("WRA_CLEAN_READ_MODE", "")).strip().lower() in {"1", "true", "yes", "on"},
        help="Prefer *_clean fields from cars.data while building documents",
    )
    parser.add_argument(
        "--preflight-gate",
        action="store_true",
        default=str(os.environ.get("WRA_MEILI_PREFLIGHT_GATE", "")).strip().lower() in {"1", "true", "yes", "on"},
        help="Run DB quality gates before syncing documents",
    )
    parser.add_argument(
        "--preflight-min-price-coverage-pct",
        type=float,
        default=_env_float("WRA_MEILI_PREFLIGHT_MIN_PRICE_COVERAGE_PCT", 97.0),
    )
    parser.add_argument(
        "--preflight-min-brand-coverage-pct",
        type=float,
        default=_env_float("WRA_MEILI_PREFLIGHT_MIN_BRAND_COVERAGE_PCT", 99.0),
    )
    parser.add_argument(
        "--preflight-min-model-coverage-pct",
        type=float,
        default=_env_float("WRA_MEILI_PREFLIGHT_MIN_MODEL_COVERAGE_PCT", 99.0),
    )
    args = parser.parse_args()

    mk = (args.meili_key or "").strip()
    args.meili_key = mk if mk else None

    settings_path = args.settings
    if not settings_path.is_file():
        parser.error(f"settings file not found: {settings_path}")

    try:
        since_dt = _optional_since(args.since)
    except ValueError as e:
        parser.error(str(e))

    live_uid = (args.live_index_name or "cars").strip()
    build_uid = (args.index_name or "cars").strip()
    if args.swap_into_live:
        if args.settings_only:
            parser.error("--swap-into-live cannot be combined with --settings-only")
        if live_uid == build_uid:
            parser.error("--swap-into-live requires different --index-name (build/staging) and --live-index-name")

    if not args.pg_dsn and not args.settings_only:
        parser.error("--pg-dsn is required unless --settings-only")
    if args.preflight_gate and not args.settings_only:
        env = dict(os.environ)
        env.setdefault("DATABASE_URL", str(args.pg_dsn or ""))
        script_path = _BACKEND_MEILI / "scripts" / "meili_sync_preflight.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--min-price-coverage-pct",
            str(args.preflight_min_price_coverage_pct),
            "--min-brand-coverage-pct",
            str(args.preflight_min_brand_coverage_pct),
            "--min-model-coverage-pct",
            str(args.preflight_min_model_coverage_pct),
        ]
        proc = subprocess.run(cmd, env=env, check=False)
        if proc.returncode != 0:
            raise SystemExit(proc.returncode)

    settings = load_settings(settings_path)
    client = Client(args.meili_url, args.meili_key)

    try:
        if args.swap_into_live:
            ensure_index(client, live_uid, recreate=False)
        ensure_index(client, build_uid, recreate=args.recreate_index)
        apply_settings(client, build_uid, settings)

        if args.settings_only:
            print(f"settings applied to index {build_uid!r}", flush=True)
            return

        assert args.pg_dsn
        n = push_batches(
            client,
            build_uid,
            args.pg_dsn,
            since=since_dt,
            batch_size=max(1, min(args.batch_size, 50_000)),
            wait_each_batch=not args.no_wait_batches,
            clean_read_mode=bool(args.clean_read_mode),
        )
        print(f"synced document batches (upsert count): {n}", flush=True)
        if args.swap_into_live:
            print(f"swapping Meilisearch indexes {live_uid!r} <-> {build_uid!r}", flush=True)
            swap_task = client.swap_indexes([{"indexes": [live_uid, build_uid]}])
            client.wait_for_task(swap_task.task_uid, timeout_in_ms=1_800_000)
            print(
                f"swap complete: index {live_uid!r} now serves the data built into {build_uid!r}",
                flush=True,
            )
    except MeilisearchApiError as e:
        if "invalid_api_key" in str(e).lower():
            print("Meilisearch: invalid_api_key.", file=sys.stderr)
            print(_MEILI_INVALID_KEY_HINT, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

