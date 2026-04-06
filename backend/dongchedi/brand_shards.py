"""Числовые brand для поля form `brand` в sh_sku_list — обход лимита ~10k без фильтра.

Полный листинг без brand на стороне API часто обрывается на has_more=false при ~10 000 строк;
отдельные запросы по маркам дают независимые окна. Значения 1…200 покрывают большинство
индексов брендов в каталоге 懂车帝; пустые brand просто дадут короткий цикл по страницам.

Точечный список задайте в dongchedi_scraper.yaml: `brand_ids: [\"4\", \"16\", ...]`."""

from __future__ import annotations

# Подмножество «плотных» id + типичные китайские/импорт (можно заменить списком из YAML).
_DEFAULT_EXTRA: tuple[int, ...] = (
    63,
    73,
    112,
    152,
    154,
    183,
    208,
    215,
    282,
)

_DEFAULT_RANGE = tuple(range(1, 151))
_DEFAULT_SET = sorted(frozenset(_DEFAULT_RANGE) | frozenset(_DEFAULT_EXTRA))
DEFAULT_BRAND_SHARD_IDS: tuple[str, ...] = tuple(str(x) for x in _DEFAULT_SET)
