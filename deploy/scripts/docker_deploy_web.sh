#!/usr/bin/env bash
# Деплой только фронта — не пересобирает api/postgres/meili.
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose build web
docker compose up -d --no-deps web
docker compose ps web
