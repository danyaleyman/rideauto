#!/usr/bin/env bash
# Обёртка для systemd/cron: выполняет команду, пишет метрики в textfile для node_exporter.
#
# Переменные:
#   JOB_NAME          — метка job (по умолчанию wra_catalog_job)
#   WRA_JOB_METRICS_TEXTFILE — путь *.prom (если пусто — только код выхода команды)
#   ROOT              — корень репо (по умолчанию /opt/rideauto)
#
# Пример в systemd (override):
#   Environment=WRA_JOB_METRICS_TEXTFILE=/var/lib/node_exporter/textfile_collector/wra_meilisearch_sync.prom
#   Environment=JOB_NAME=wra_meilisearch_sync
#   ExecStart=/bin/bash /opt/rideauto/deploy/scripts/run_with_prometheus_job_metrics.sh \
#     /usr/bin/python3 /opt/rideauto/infrastructure/meilisearch/sync_meilisearch.py ...
#
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
JOB_NAME="${JOB_NAME:-wra_catalog_job}"
TEXTFILE="${WRA_JOB_METRICS_TEXTFILE:-}"

if [[ $# -lt 1 ]]; then
  echo "usage: JOB_NAME=... WRA_JOB_METRICS_TEXTFILE=... $0 <command> [args...]" >&2
  exit 2
fi

start="$(date +%s)"
set +e
"$@"
exit_code=$?
set -e
end="$(date +%s)"
duration="$(awk "BEGIN { print $end - $start }")"

export JOB_NAME
export EXIT_CODE="$exit_code"
export DURATION_SEC="$duration"

if [[ -n "${TEXTFILE// /}" ]]; then
  PY="${ROOT}/backend/scripts/prometheus_job_textfile.py"
  if [[ -f "$PY" ]]; then
    /usr/bin/python3 "$PY" || true
  else
    echo "run_with_prometheus_job_metrics: missing $PY" >&2
  fi
fi

exit "$exit_code"
