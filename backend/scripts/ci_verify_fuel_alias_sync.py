#!/usr/bin/env python3
"""Проверка: web/src/lib/fuel_label_aliases.json совпадает с data/fuel_label_aliases.json (байтово)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    src = repo / "data/fuel_label_aliases.json"
    dst = repo / "web/src/lib/fuel_label_aliases.json"
    if not src.is_file():
        print("missing:", src, file=sys.stderr)
        return 1
    if not dst.is_file():
        print("missing:", dst, file=sys.stderr)
        print("hint: npm run sync-static-data (inside web)", file=sys.stderr)
        return 1
    hs = hashlib.sha256(src.read_bytes()).hexdigest()
    wd = hashlib.sha256(dst.read_bytes()).hexdigest()
    if hs != wd:
        print("fuel_label_aliases mismatch: sync web from data", file=sys.stderr)
        print("  ", src, hs, sep="\t", file=sys.stderr)
        print("  ", dst, wd, sep="\t", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
