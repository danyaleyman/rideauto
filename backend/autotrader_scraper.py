"""
Autotrader USA: SRP pages + VDP enrich → Postgres (source=autotrader).

Отдельный контур от Encar/Che168. Cookie/Akamai: AUTOTRADER_COOKIE или cookie_file.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, List, Optional

# Ensure backend/ is on path when run as script
_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from encar_scraper import load_config  # noqa: E402
from scraper_pipeline.autotrader.client import AsyncAutotraderClient  # noqa: E402
from scraper_pipeline.autotrader.workers import (  # noqa: E402
    load_vdp_html_map,
    run_autotrader_ingest,
    run_autotrader_offline_ingest,
)
from scraper_pipeline.encar.savers import build_car_saver  # noqa: E402


class _FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


def setup_logging(cfg: dict) -> logging.Logger:
    log_cfg = cfg.get("logging", {})
    level = getattr(logging, str(log_cfg.get("level", "INFO")).upper(), logging.INFO)
    fmt = log_cfg.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handlers: List[logging.Handler] = [_FlushingStreamHandler()]
    handlers[0].setFormatter(logging.Formatter(fmt))
    log_file = log_cfg.get("file")
    if log_file:
        lp = Path(log_file)
        if not lp.is_absolute():
            lp = _BACKEND.parent / lp
        try:
            lp.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(lp, encoding="utf-8")
            fh.setFormatter(logging.Formatter(fmt))
            handlers.append(fh)
        except OSError as e:
            sys.stderr.write(f"autotrader_scraper: log file {lp}: {e}\n")
    logging.basicConfig(level=level, format=fmt, handlers=handlers, force=True)
    return logging.getLogger("autotrader_scraper")


async def run_scraper(
    config_path: str,
    *,
    max_pages: Optional[int] = None,
    max_cars: Optional[int] = None,
    srp_html_path: Optional[str] = None,
    vdp_html_paths: Optional[List[str]] = None,
    preloaded_config: Optional[dict] = None,
) -> None:
    config = preloaded_config if isinstance(preloaded_config, dict) else load_config(config_path)
    if max_pages is not None:
        config.setdefault("autotrader", {})["max_pages"] = max_pages
    if max_cars is not None:
        config.setdefault("autotrader", {})["max_cars"] = max_cars

    run_id = time.strftime("at-%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    log = setup_logging(config)
    log.info("Autotrader scraper start run_id=%s config=%s", run_id, config_path)

    storage = config.get("storage") or {}
    if not storage.get("count_cars_source"):
        storage["count_cars_source"] = "autotrader"
        config["storage"] = storage

    saver, _backend = build_car_saver(config)
    try:
        if srp_html_path:
            srp_path = Path(srp_html_path)
            if not srp_path.is_file():
                raise FileNotFoundError(f"SRP HTML not found: {srp_path}")
            srp_html = srp_path.read_text(encoding="utf-8")
            vdp_map = load_vdp_html_map(*(vdp_html_paths or []))
            at = config.get("autotrader") or {}
            limit = int(at.get("max_cars") or 0) or 0
            log.info("Offline ingest from %s (vdp=%s max_cars=%s)", srp_path, len(vdp_map), limit)
            stats = await run_autotrader_offline_ingest(
                saver,
                srp_html=srp_html,
                vdp_by_id=vdp_map,
                max_cars=limit,
                logger=log,
            )
            log.info("Autotrader offline done: %s", stats.as_dict())
            return

        # Session is minted in main() before asyncio.run (Playwright sync API).
        client = AsyncAutotraderClient(config, logger=log, auto_bootstrap=True)
        try:
            await client.open()
            stats = await run_autotrader_ingest(client, saver, config, logger=log)
            log.info("Autotrader done: %s", stats.as_dict())
        finally:
            await client.close()
    finally:
        close = getattr(saver, "close", None)
        if callable(close):
            close()


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Autotrader USA catalog ingest")
    p.add_argument(
        "--config",
        default=os.environ.get("AUTOTRADER_CONFIG", "autotrader_scraper.yaml"),
        help="YAML config path (repo root or absolute)",
    )
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--max-cars", type=int, default=None)
    p.add_argument(
        "--srp-html",
        default=None,
        help="Offline: path to saved SRP HTML (no network / Akamai)",
    )
    p.add_argument(
        "--vdp-html",
        action="append",
        default=None,
        help="Offline: VDP HTML file(s); may be repeated. Filename vdp_<id>_*.html preferred.",
    )
    args = p.parse_args(argv)

    cfg_path = args.config
    cand = Path(cfg_path)
    if not cand.is_file():
        alt = _BACKEND.parent / cfg_path
        if alt.is_file():
            cfg_path = str(alt)

    try:
        config = load_config(cfg_path)
        log = setup_logging(config)
        # Playwright sync bootstrap must run outside the asyncio event loop.
        if not args.srp_html:
            from scraper_pipeline.autotrader.session import ensure_autotrader_session

            ensure_autotrader_session(config, log)
        asyncio.run(
            run_scraper(
                cfg_path,
                max_pages=args.max_pages,
                max_cars=args.max_cars,
                srp_html_path=args.srp_html,
                vdp_html_paths=args.vdp_html,
                preloaded_config=config,
            )
        )
    except KeyboardInterrupt:
        return 130
    except Exception:
        logging.getLogger("autotrader_scraper").exception("fatal")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
