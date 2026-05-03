#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/rideauto"
cd "$ROOT"

: "${DATABASE_URL:?DATABASE_URL is required for parser audit}"

LIMIT="${PARSER_AUDIT_LIMIT:-20}"
HISTORY_FILE="${PARSER_AUDIT_HISTORY_FILE:-$ROOT/backend/data/encar_parser_audit_history.jsonl}"
MAX_MISSING_REQUIRED_PCT="${PARSER_AUDIT_MAX_MISSING_REQUIRED_PCT:-2.0}"
MAX_MISSING_REQUIRED_DELTA_PCT="${PARSER_AUDIT_MAX_MISSING_REQUIRED_DELTA_PCT:-0.5}"
MIN_SCHEMA_COVERAGE_PCT="${PARSER_AUDIT_MIN_SCHEMA_COVERAGE_PCT:-95.0}"
SLACK_WEBHOOK="${PARSER_AUDIT_SLACK_WEBHOOK:-}"
SLACK_CHANNEL="${PARSER_AUDIT_SLACK_CHANNEL:-}"
# Опционально: OPS_TELEGRAM_BOT_TOKEN + OPS_TELEGRAM_CHAT_ID (или PARSER_AUDIT_TELEGRAM_*)
MAX_MONTHLY_SHARE_DELTA_PCT="${PARSER_AUDIT_MAX_MONTHLY_SHARE_DELTA_PCT:-3.0}"
MAX_RESERVED_SHARE_DELTA_PCT="${PARSER_AUDIT_MAX_RESERVED_SHARE_DELTA_PCT:-2.0}"
KEEP_HISTORY_DAYS="${PARSER_AUDIT_KEEP_HISTORY_DAYS:-7}"
CASE_FILE="${PARSER_PRICE_INTENT_CASES_FILE:-$ROOT/backend/data/encar_price_intent_cases.json}"
CASE_CHECK_TIMEOUT="${PARSER_PRICE_INTENT_CASE_TIMEOUT_SEC:-12.0}"

set +e
AUDIT_EXIT=0
CASE_EXIT=0

/usr/bin/python3 backend/scripts/encar_parser_audit.py \
  --limit "$LIMIT" \
  --history-file "$HISTORY_FILE" \
  --keep-history-days "$KEEP_HISTORY_DAYS" \
  --fail-on-regression \
  --max-missing-required-pct "$MAX_MISSING_REQUIRED_PCT" \
  --max-missing-required-delta-pct "$MAX_MISSING_REQUIRED_DELTA_PCT" \
  --min-schema-coverage-pct "$MIN_SCHEMA_COVERAGE_PCT" \
  --max-monthly-share-delta-pct "$MAX_MONTHLY_SHARE_DELTA_PCT" \
  --max-reserved-share-delta-pct "$MAX_RESERVED_SHARE_DELTA_PCT" \
  --slack-webhook-url "$SLACK_WEBHOOK" \
  --slack-channel "$SLACK_CHANNEL"
AUDIT_EXIT=$?

if [[ -f "$CASE_FILE" ]]; then
  /usr/bin/python3 backend/scripts/encar_price_intent_case_check.py \
    --config scraper_config.yaml \
    --cases-file "$CASE_FILE" \
    --timeout-sec "$CASE_CHECK_TIMEOUT"
  CASE_EXIT=$?
else
  echo "price-intent case file not found, skipping: $CASE_FILE"
fi

if [[ $AUDIT_EXIT -ne 0 ]]; then
  exit "$AUDIT_EXIT"
fi
exit "$CASE_EXIT"
