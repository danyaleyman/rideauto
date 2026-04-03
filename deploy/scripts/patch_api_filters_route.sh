#!/usr/bin/env bash
# Добавляет app.router.add_get("/api/filters", facets) в main() после create_app().
# Использование на сервере: bash deploy/scripts/patch_api_filters_route.sh /opt/prod-encar/backend/api_server.py
set -euo pipefail
TARGET="${1:-backend/api_server.py}"
cp -a "$TARGET" "${TARGET}.bak.$(date +%Y%m%d%H%M%S)"
python3 - "$TARGET" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
if "def main()" not in text:
    print("error: def main() not found", file=sys.stderr)
    sys.exit(1)
needle = "    app = create_app(db_path)\n    web.run_app(app, host=args.host, port=args.port)"
replacement = (
    "    app = create_app(db_path)\n"
    '    app.router.add_get("/api/filters", facets)\n'
    "    web.run_app(app, host=args.host, port=args.port)"
)
if 'app.router.add_get("/api/filters", facets)' in text:
    print("already has /api/filters registration, ok")
    sys.exit(0)
if needle not in text:
    print("error: exact main() tail not found — edit manually or restore from .bak", file=sys.stderr)
    sys.exit(1)
path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
print("patched:", path)
PY
echo "Restart: sudo systemctl restart encar-api.service"
