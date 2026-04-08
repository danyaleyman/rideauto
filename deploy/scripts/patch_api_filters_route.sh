#!/usr/bin/env bash
# Исторический скрипт: в текущем стеке FastAPI маршрут уже есть в
# backend/fastapi_app/routers/facets.py (`GET /api/filters`).
set -euo pipefail
echo "Ничего не делаем: /api/filters обслуживает fastapi_app (см. routers/facets.py)."
echo "Перезапуск API: sudo systemctl restart prod-encar-api.service  # или ваш unit"
