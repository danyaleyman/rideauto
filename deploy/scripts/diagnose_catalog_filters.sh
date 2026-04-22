#!/usr/bin/env bash
set -u

ROOT="${1:-/opt/prod-encar}"
API_BASE="${API_BASE:-http://127.0.0.1:8080}"
SINCE="${SINCE:-15m}"

cd "$ROOT" || {
  echo "ERROR: cannot cd to $ROOT"
  exit 2
}

echo "=== Catalog filters diagnose ==="
echo "root=$ROOT"
echo "api_base=$API_BASE"
echo "since=$SINCE"
echo

echo "=== docker compose ps ==="
docker compose ps || true
echo

echo "=== API health ==="
curl -sS -m 15 "$API_BASE/api/health" || true
echo
echo

echo "=== API search smoke (korea) ==="
SEARCH_URL="$API_BASE/api/search?per_page=1&region=korea&source=encar&sort=date_new"
echo "$SEARCH_URL"
curl -sS -m 20 "$SEARCH_URL" | python3 -m json.tool 2>/dev/null | sed -n '1,80p' || curl -sS -m 20 "$SEARCH_URL" | sed -n '1,20p'
echo
echo

echo "=== API facets smoke (korea) ==="
FACETS_URL="$API_BASE/api/facets?region=korea&source=encar"
echo "$FACETS_URL"
curl -sS -m 20 "$FACETS_URL" | python3 -m json.tool 2>/dev/null | sed -n '1,120p' || curl -sS -m 20 "$FACETS_URL" | sed -n '1,20p'
echo
echo

echo "=== API search smoke (china) ==="
SEARCH_CN_URL="$API_BASE/api/search?per_page=1&region=china&source=china&sort=date_new"
echo "$SEARCH_CN_URL"
curl -sS -m 20 "$SEARCH_CN_URL" | python3 -m json.tool 2>/dev/null | sed -n '1,80p' || curl -sS -m 20 "$SEARCH_CN_URL" | sed -n '1,20p'
echo
echo

echo "=== API facets smoke (china) ==="
FACETS_CN_URL="$API_BASE/api/facets?region=china&source=china"
echo "$FACETS_CN_URL"
curl -sS -m 20 "$FACETS_CN_URL" | python3 -m json.tool 2>/dev/null | sed -n '1,120p' || curl -sS -m 20 "$FACETS_CN_URL" | sed -n '1,20p'
echo
echo

echo "=== Redis replication role ==="
docker compose exec -T redis redis-cli INFO replication 2>/dev/null | sed -n '1,40p' || true
echo

echo "=== API log scan ($SINCE) ==="
docker compose logs --since "$SINCE" api 2>/dev/null | rg -n -i "ReadOnlyError|cache get failed|cache set failed|facet dimension failed|Traceback| 500 |ERROR" || echo "(no matched API errors)"
echo

echo "=== WEB log scan ($SINCE) ==="
docker compose logs --since "$SINCE" web 2>/dev/null | rg -n -i "facets fetch failed|search fetch failed|TypeError|ERROR" || echo "(no matched WEB errors)"
echo

echo "=== Client event logs from PostgreSQL (last 30 min) ==="
docker compose exec -T postgres sh -lc "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" <<'SQL'
SELECT
  to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS ts,
  event_type,
  left(session_id, 12) AS session,
  pathname,
  payload
FROM web_client_events
WHERE created_at >= now() - interval '30 minutes'
ORDER BY created_at DESC
LIMIT 120;
SQL" 2>/dev/null || echo "(table web_client_events not found or query failed)"
echo

echo "=== Client event summary by type (last 30 min) ==="
docker compose exec -T postgres sh -lc "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" <<'SQL'
SELECT event_type, count(*)::int AS cnt
FROM web_client_events
WHERE created_at >= now() - interval '30 minutes'
GROUP BY event_type
ORDER BY cnt DESC, event_type ASC
LIMIT 50;
SQL" 2>/dev/null || echo "(table web_client_events not found or query failed)"
echo

echo "=== Done ==="
