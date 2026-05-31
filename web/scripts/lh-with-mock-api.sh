#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
node "$ROOT/e2e/serve-mock-api.mjs" &
MOCK_PID=$!
trap 'kill "$MOCK_PID" 2>/dev/null || true' EXIT
sleep 1
cd "$ROOT/web"
export WRA_API_INTERNAL=http://127.0.0.1:28765
exec npm run start -- --port 3099 --hostname 127.0.0.1
