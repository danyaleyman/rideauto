"""Che168 Global API language policy: EN ingest only."""

from __future__ import annotations

import logging

from localization.term_localizer import _offline_translate, localize_china_option_label
from scraper_pipeline.che168.client import resolve_che168_api_language


def test_resolve_che168_api_language_forces_en() -> None:
    log = logging.getLogger("test.che168.lang")
    assert resolve_che168_api_language("en", log) == "en"
    assert resolve_che168_api_language("EN-US", log) == "en"
    assert resolve_che168_api_language("ru", log) == "en"
    assert resolve_che168_api_language("zh", log) == "en"
    assert resolve_che168_api_language("", log) == "en"


def test_en_to_ru_offline_terms() -> None:
    assert _offline_translate("Gasoline", target_lang="ru") == "Бензин"
    assert _offline_translate("gasoline", target_lang="ru") == "Бензин"
    assert _offline_translate("Automatic", target_lang="ru") == "Автомат"
    assert _offline_translate("SUV", target_lang="ru") == "Внедорожник (SUV)"
    assert localize_china_option_label("Blind Spot Monitoring") == "Контроль слепых зон"
