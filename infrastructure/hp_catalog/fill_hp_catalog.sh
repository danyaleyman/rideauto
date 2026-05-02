#!/usr/bin/env bash
# Запуск из корня репозитория: добивает data/hp_catalog.db через DeepSeek/OpenAI.
# Требует DEEPSEEK_API_KEY и/или OPENAI_API_KEY в окружении.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${ROOT}/backend"
cd "$ROOT"
exec python3 backend/scripts/fill_hp_catalog_deepseek.py "$@"
