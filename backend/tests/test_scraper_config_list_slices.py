"""Регресс-тесты на list_q_suffixes: они молча ломали discovery (инцидент 2026-10-10).

Все 15 брендовых срезов давали 404 на `offset=0` (формат `_.(And.Manu.[현대].)`), 404 не входит в
`retry_statuses`, поэтому срез выходил сразу, а discovery делала 2 запроса вместо 32. Проверяем
формат, который прод подтвердил ответом `200 + count`.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[2] / "scraper_config.yaml"

# Прод 2026-10-10: "_.Manufacturer.현대." -> 200 count=47744; "_.(And.Manu.[현대].)" -> 404.
_OK_SUFFIX = re.compile(r"^_\..+\.$")


def _suffixes() -> list[str]:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    return list((cfg.get("http") or {}).get("list_q_suffixes") or [])


def test_first_suffix_empty_for_checkpoint_compat() -> None:
    # Ключ чекпоинта — "{car_type}_v{index}": индекс 0 обязан остаться базовым срезом.
    assert _suffixes()[0] == ""


def test_no_bracket_syntax_in_suffixes() -> None:
    bad = [s for s in _suffixes() if "[" in s or "]" in s]
    assert bad == [], f"скобки вокруг значения ломают матчинг Encar: {bad}"


def test_no_short_manu_alias_in_suffixes() -> None:
    bad = [s for s in _suffixes() if "Manu." in s or ".Manu]" in s]
    assert bad == [], f"сокращение Manu. даёт 404: {bad}"


def test_suffixes_are_well_formed() -> None:
    for s in _suffixes():
        if s == "":
            continue
        assert _OK_SUFFIX.match(s), f"срез не похож на рабочий: {s!r}"
        assert s.endswith(".)") or s.endswith("."), f"срез не закрыт: {s!r}"


def test_suffixes_unique_and_cover_key_brands() -> None:
    suffixes = _suffixes()
    assert len(suffixes) == len(set(suffixes)), "дубликаты срезов = лишние запросы"
    joined = " ".join(suffixes)
    for brand in ("현대", "기아", "제네시스", "BMW", "벤츠", "도요타", "KG모빌리티(쌍용)", "르노코리아(삼성)"):
        assert f"_.Manufacturer.{brand}." in joined, f"нет среза по бренду {brand}"
