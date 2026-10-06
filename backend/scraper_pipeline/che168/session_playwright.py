"""
Получение кук Che168 Global через Chromium (Playwright) на том же исходящем IP, что и API.

Реализация вынесена в scraper_pipeline.resilience.session_provider (Session Platform).
Этот модуль — совместимый фасад для существующих импортов.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from scraper_pipeline.resilience.session_provider import (
    apply_playwright_bootstrap_to_config as _apply_bootstrap,
    playwright_proxy_config,
)


def bootstrap_che168_browser_cookies_sync(
    config: dict,
    log: logging.Logger,
) -> Tuple[Dict[str, str], Optional[str]]:
    """Совместимость: (cookies, proxy_url) как раньше."""
    from scraper_pipeline.resilience.session_provider import Che168SessionProvider

    bundle = Che168SessionProvider().acquire(config, log)
    return dict(bundle.cookies), bundle.proxy_url


def apply_playwright_bootstrap_to_config(config: dict, log: logging.Logger) -> None:
    """Мутирует config: cookies + опционально _session_proxy_url для AsyncChe168Client."""
    _apply_bootstrap(config, log)


__all__ = [
    "apply_playwright_bootstrap_to_config",
    "bootstrap_che168_browser_cookies_sync",
    "playwright_proxy_config",
]
