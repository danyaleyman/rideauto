from __future__ import annotations

from typing import Any, Dict


def slim_catalog_car(car: Dict[str, Any], car_id: str) -> Dict[str, Any]:
    """Обёртка над api_server._slim_catalog_car — один источник правды для плитки каталога."""
    from api_server import _slim_catalog_car  # noqa: WPS433 — runtime import из монолита

    return _slim_catalog_car(car, car_id)
