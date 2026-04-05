"""Парсинг листинга б/у с www.dongchedi.com (motor/pc/sh/sh_sku_list + карточка __NEXT_DATA__)."""

from dongchedi.normalize import sku_row_to_payload

__all__ = ["sku_row_to_payload"]
