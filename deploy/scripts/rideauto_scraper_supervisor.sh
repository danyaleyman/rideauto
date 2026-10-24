#!/usr/bin/env bash
# Keep market scrapers alive until work is done; restart on death/stall; periodic catalog sync.
#
#   nohup bash /opt/rideauto/deploy/scripts/rideauto_scraper_supervisor.sh >>/opt/rideauto/logs/supervisor.log 2>&1 &
#   # or: systemctl enable --now rideauto-scraper-supervisor.service
#
# Env (optional):
#   WRA_SUPERVISOR_INTERVAL_SEC=120
#   WRA_SUPERVISOR_STALL_SEC=1200
#   WRA_SUPERVISOR_CATALOG_EVERY_SEC=1800
set -euo pipefail

ROOT="${ROOT:-/opt/rideauto}"
LOG_DIR="${ROOT}/logs/overnight"
STATE_DIR="${ROOT}/logs/supervisor_state"
mkdir -p "$LOG_DIR" "$STATE_DIR"

INTERVAL="${WRA_SUPERVISOR_INTERVAL_SEC:-120}"
STALL_SEC="${WRA_SUPERVISOR_STALL_SEC:-1200}"
CATALOG_EVERY="${WRA_SUPERVISOR_CATALOG_EVERY_SEC:-1800}"
PY="${ROOT}/.venv/bin/python"
export PYTHONUNBUFFERED=1
export PYTHONPATH="${ROOT}/backend"

log() { echo "$(date -Is) [supervisor] $*"; }

load_env() {
  set -a
  [[ -f /etc/default/rideauto ]] && . /etc/default/rideauto
  [[ -f "${ROOT}/.env" ]] && . "${ROOT}/.env"
  set +a
}

pg_counts() {
  load_env
  "$PY" - <<'PY'
import os, subprocess, psycopg2
dsn = os.environ.get("SYNC_PG_DSN") or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN")
r = "/opt/rideauto/deploy/scripts/pg_dsn_host_local_rewrite.py"
if os.path.isfile(r) and dsn:
    dsn = subprocess.check_output(["python3", r], input=dsn.encode()).decode().strip()
conn = psycopg2.connect(dsn)
cur = conn.cursor()
cur.execute("SELECT coalesce(source,''), count(*) FROM cars GROUP BY 1")
rows = dict(cur.fetchall())
cur.execute(
    """
    SELECT count(*) FROM scraper_checkpoint_pending
    WHERE scope = 'che168'
    """
)
# fallback if table/name differs
try:
    che_pending = cur.fetchone()[0]
except Exception:
    che_pending = -1
conn.close()
print(rows.get("encar", 0), rows.get("che168", 0), rows.get("autotrader", 0), che_pending)
PY
}

# Checkpoint pending helper (Encar/Che168 use cars_scraper_checkpoint or similar)
pending_for_scope() {
  local scope="$1"
  load_env
  "$PY" - <<PY
import os, subprocess, psycopg2
dsn = os.environ.get("SYNC_PG_DSN") or os.environ.get("DATABASE_URL") or os.environ.get("WRA_PG_DSN")
r = "/opt/rideauto/deploy/scripts/pg_dsn_host_local_rewrite.py"
if os.path.isfile(r) and dsn:
    dsn = subprocess.check_output(["python3", r], input=dsn.encode()).decode().strip()
conn = psycopg2.connect(dsn)
cur = conn.cursor()
n = -1
for sql in (
    "SELECT count(*) FROM scraper_checkpoint WHERE scope=%s AND status='pending'",
    "SELECT pending_count FROM scraper_checkpoint_meta WHERE scope=%s",
    "SELECT count(*) FROM checkpoint_pending WHERE scope=%s",
):
    try:
        cur.execute(sql, ("""$scope""",))
        row = cur.fetchone()
        if row is not None:
            n = int(row[0] or 0)
            break
    except Exception:
        conn.rollback()
conn.close()
print(n)
PY
}

# Parse progress fingerprint from latest log for a market
progress_fp() {
  local pattern="$1"
  local logfile
  logfile=$(ls -t ${LOG_DIR}/${pattern}_*.log 2>/dev/null | head -1 || true)
  if [[ -z "${logfile}" || ! -f "$logfile" ]]; then
    echo "none"
    return
  fi
  # last saved/total or Stats line
  local line
  line=$(grep -E 'saved total=|Stats:|browser SRP page=|ingest done' "$logfile" | tail -1 || true)
  local mtime
  mtime=$(stat -c %Y "$logfile" 2>/dev/null || echo 0)
  echo "${mtime}|${line}"
}

is_running() {
  local pattern="$1"
  pgrep -f "$pattern" >/dev/null 2>&1
}

start_encar() {
  local stamp logfile
  stamp=$(date -u +%Y%m%d-%H%M%S)
  logfile="${LOG_DIR}/encar_sup_${stamp}.log"
  touch "$logfile"
  chown rideauto:rideauto "$logfile" 2>/dev/null || true
  log "START encar -> $logfile"
  sudo -u rideauto env HOME=/var/lib/rideauto PYTHONUNBUFFERED=1 PYTHONPATH="${ROOT}/backend" \
    bash -lc "set -a; . /etc/default/rideauto; . ${ROOT}/.env; set +a; cd ${ROOT}; nohup ${PY} ${ROOT}/backend/encar_scraper.py --config ${ROOT}/scraper_config.yaml --max-cars 0 >>'$logfile' 2>&1 &"
}

start_che168() {
  local stamp logfile
  stamp=$(date -u +%Y%m%d-%H%M%S)
  logfile="${LOG_DIR}/che168_sup_${stamp}.log"
  touch "$logfile"
  chown rideauto:rideauto "$logfile" 2>/dev/null || true
  # Prefer draining pending queue (full result) over endless list-only.
  log "START che168 --only-pending -> $logfile"
  sudo -u rideauto env HOME=/var/lib/rideauto PYTHONUNBUFFERED=1 PYTHONPATH="${ROOT}/backend" \
    bash -lc "set -a; . /etc/default/rideauto; . ${ROOT}/.env; set +a; cd ${ROOT}; nohup ${PY} ${ROOT}/backend/che168_scraper.py --config ${ROOT}/che168_scraper.yaml --only-pending >>'$logfile' 2>&1 &"
}

start_autotrader() {
  local stamp logfile
  stamp=$(date -u +%Y%m%d-%H%M%S)
  logfile="${LOG_DIR}/autotrader_sup_${stamp}.log"
  touch "$logfile"
  chown rideauto:rideauto "$logfile" 2>/dev/null || true
  log "START autotrader -> $logfile"
  sudo -u rideauto env HOME=/var/lib/rideauto PYTHONUNBUFFERED=1 PYTHONPATH="${ROOT}/backend" \
    bash -lc "set -a; . /etc/default/rideauto; . ${ROOT}/.env; set +a; cd ${ROOT}; nohup ${PY} ${ROOT}/backend/autotrader_scraper.py --config ${ROOT}/autotrader_scraper.yaml >>'$logfile' 2>&1 &"
}

maybe_restart() {
  local name="$1" pattern="$2" start_fn="$3"
  local state="${STATE_DIR}/${name}.fp"
  local now fp prev prev_ts

  if ! is_running "$pattern"; then
    log "$name: not running -> start"
    "$start_fn"
    echo "$(date +%s)|started" >"$state"
    return
  fi

  fp=$(progress_fp "$name")
  now=$(date +%s)
  if [[ -f "$state" ]]; then
    prev=$(cat "$state")
    prev_ts=${prev%%|*}
    if [[ "$fp" == "${prev#*|}" ]] || [[ "$fp" == "$prev" ]]; then
      # same fingerprint content — check stall by mtime embedded
      local file_mtime=${fp%%|*}
      if [[ "$file_mtime" =~ ^[0-9]+$ ]] && (( now - file_mtime > STALL_SEC )); then
        log "$name: STALL ${STALL_SEC}s (no log progress) -> restart"
        pkill -f "$pattern" || true
        sleep 2
        "$start_fn"
        echo "${now}|restarted_stall" >"$state"
        return
      fi
    fi
  fi
  echo "${now}|${fp}" >"$state"
  log "$name: ok running"
}

run_catalog_if_due() {
  local marker="${STATE_DIR}/last_catalog_sync"
  local now last=0
  now=$(date +%s)
  [[ -f "$marker" ]] && last=$(cat "$marker" || echo 0)
  if (( now - last >= CATALOG_EVERY )); then
    log "catalog pipeline kick"
    if bash "${ROOT}/deploy/scripts/run_catalog_pipeline_host.sh" >>"${LOG_DIR}/catalog_supervisor.log" 2>&1; then
      log "catalog pipeline ok"
    else
      log "catalog pipeline failed; trying meili-only"
      bash /tmp/rideauto_meili_sync.sh >>"${LOG_DIR}/catalog_supervisor.log" 2>&1 || \
        "${ROOT}/.venv/bin/python" "${ROOT}/infrastructure/meilisearch/sync_meilisearch.py" --help >/dev/null || true
    fi
    echo "$now" >"$marker"
  fi
}

log "boot interval=${INTERVAL}s stall=${STALL_SEC}s catalog_every=${CATALOG_EVERY}s"
load_env

while true; do
  # Map log prefixes used by overnight/supervisor launches
  # progress_fp looks for ${name}_*.log — use loose patterns via symlinks/latest
  for pair in \
    "encar:backend/encar_scraper.py:start_encar" \
    "che168:backend/che168_scraper.py:start_che168" \
    "autotrader:backend/autotrader_scraper.py:start_autotrader"
  do
    IFS=: read -r name pattern start_fn <<<"$pair"
    # Refresh "latest" log pointers for stall detection across naming schemes
    latest=$(ls -t ${LOG_DIR}/${name}_*.log 2>/dev/null | head -1 || true)
    if [[ -n "$latest" ]]; then
      ln -sfn "$latest" "${LOG_DIR}/${name}_latest.log" || true
    fi
    maybe_restart "$name" "$pattern" "$start_fn" || log "$name: restart helper error"
  done
  run_catalog_if_due || true
  sleep "$INTERVAL"
done
