#!/usr/bin/env python3
"""CLI health probes for Scraper Resilience Platform (TLS / session / list)."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main() -> int:
    ap = argparse.ArgumentParser(description="RideAuto scraper resilience probes")
    ap.add_argument("--source", choices=("che168", "encar"), required=True)
    ap.add_argument(
        "--config",
        default="",
        help="Path to scraper YAML (default: che168_scraper.yaml / scraper_config.yaml)",
    )
    ap.add_argument("--json", action="store_true", help="Print ProbeReport JSON")
    args = ap.parse_args()

    root = _BACKEND.parent
    if args.config:
        cfg_path = str(Path(args.config).expanduser().resolve())
    elif args.source == "che168":
        cfg_path = str(root / "che168_scraper.yaml")
    else:
        cfg_path = str(root / "scraper_config.yaml")

    # Reuse Encar load_config (extends + *.local.yaml + SCRAPER_* env).
    from encar_scraper import load_config

    config = load_config(cfg_path)

    log = logging.getLogger("resilience_probe")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from scraper_pipeline.resilience.probes import run_source_probes

    report = asyncio.run(run_source_probes(args.source, config, log))
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for r in report.results:
            mark = "OK" if r.ok else "FAIL"
            print(f"[{mark}] {r.name}: {r.detail}")
        print(f"overall={'OK' if report.ok else 'FAIL'} source={args.source}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
