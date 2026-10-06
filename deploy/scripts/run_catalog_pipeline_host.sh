#!/usr/bin/env bash
# Catalog Pipeline Platform: Postgres prices → Meilisearch (единый оркестратор).
#
# Стадии:
#   1) postgres_catalog_sync (цены + needs_pricing_recompute reset)
#   2) meilisearch sync (preflight + optional blue/green swap)
#   3) textfile метрики wra_job_last_* + lag snapshot
#
#   sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_catalog_pipeline_host.sh
#   WRA_CATALOG_PIPELINE_SKIP_PG=1 ...   # только Meili
#   WRA_CATALOG_PIPELINE_SKIP_MEILI=1 ... # только PG
#
# Рекомендуемый blue/green (не опустошает live при recreate):
#   WRA_MEILISEARCH_INDEX=cars_build
#   WRA_MEILI_LIVE_INDEX=cars
#   WRA_MEILI_SWAP_INTO_LIVE=1
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
if [[ -f /etc/default/rideauto ]]; then
  set -a
  # shellcheck source=/dev/null
  source /etc/default/rideauto
  set +a
fi

cd "$ROOT"
TEXTFILE_DIR="${WRA_JOB_METRICS_DIR:-/var/lib/node_exporter/textfile_collector}"
mkdir -p "$TEXTFILE_DIR" 2>/dev/null || true

_write_job_metrics() {
  local job_name="$1"
  local exit_code="$2"
  local started="$3"
  local ended
  ended="$(date +%s)"
  local dur=$((ended - started))
  export JOB_NAME="$job_name"
  export EXIT_CODE="$exit_code"
  export DURATION_SEC="$dur"
  export WRA_JOB_METRICS_TEXTFILE="${TEXTFILE_DIR}/${job_name}.prom"
  if [[ -f "${ROOT}/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${ROOT}/.venv/bin/activate"
  fi
  export PYTHONPATH="${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
  python "${ROOT}/backend/scripts/prometheus_job_textfile.py" || true
}

PIPELINE_START="$(date +%s)"
PG_EC=0
MEILI_EC=0

if [[ "${WRA_CATALOG_PIPELINE_SKIP_PG:-0}" != "1" ]]; then
  echo "catalog_pipeline: stage=postgres_catalog_sync" >&2
  t0="$(date +%s)"
  set +e
  bash "${ROOT}/deploy/scripts/run_postgres_catalog_sync_host.sh"
  PG_EC=$?
  set -e
  _write_job_metrics "wra_postgres_catalog_sync" "$PG_EC" "$t0"
  if [[ "$PG_EC" -ne 0 ]]; then
    echo "catalog_pipeline: postgres_catalog_sync failed exit=$PG_EC — Meili stage skipped" >&2
    _write_job_metrics "wra_catalog_pipeline" "$PG_EC" "$PIPELINE_START"
    exit "$PG_EC"
  fi
fi

if [[ "${WRA_CATALOG_PIPELINE_SKIP_MEILI:-0}" != "1" ]]; then
  echo "catalog_pipeline: stage=meilisearch_sync" >&2
  t1="$(date +%s)"
  set +e
  bash "${ROOT}/deploy/scripts/run_meilisearch_sync_host.sh" "$@"
  MEILI_EC=$?
  set -e
  _write_job_metrics "wra_meilisearch_sync" "$MEILI_EC" "$t1"
  if [[ "$MEILI_EC" -ne 0 ]]; then
    echo "catalog_pipeline: meilisearch_sync failed exit=$MEILI_EC" >&2
    _write_job_metrics "wra_catalog_pipeline" "$MEILI_EC" "$PIPELINE_START"
    exit "$MEILI_EC"
  fi
fi

# Lag / doc counts (best-effort)
if [[ -f "${ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
fi
export PYTHONPATH="${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
export WRA_CATALOG_LAG_TEXTFILE="${TEXTFILE_DIR}/wra_catalog_lag.prom"
python "${ROOT}/backend/scripts/catalog_pipeline_lag_metrics.py" || true

# Meili consistency (outbox backlog + empty index) — ADR 0004
export WRA_MEILI_CONSISTENCY_TEXTFILE="${TEXTFILE_DIR}/wra_meili_consistency.prom"
set +e
python "${ROOT}/backend/scripts/catalog_meili_consistency.py" --strict
CONS_EC=$?
set -e
if [[ "$CONS_EC" -eq 3 ]]; then
  echo "catalog_pipeline: meili consistency HARD fail exit=3" >&2
  _write_job_metrics "wra_catalog_pipeline" 3 "$PIPELINE_START"
  exit 3
fi
if [[ "$CONS_EC" -eq 2 ]]; then
  echo "catalog_pipeline: meili consistency WARN (strict)" >&2
fi

# Optional resilience probes after successful sync
if [[ "${WRA_CATALOG_PIPELINE_RUN_PROBES:-0}" == "1" ]]; then
  python "${ROOT}/backend/scripts/resilience_probes.py" --source encar || true
  python "${ROOT}/backend/scripts/resilience_probes.py" --source che168 || true
fi

_write_job_metrics "wra_catalog_pipeline" 0 "$PIPELINE_START"
echo "catalog_pipeline: OK" >&2
exit 0
