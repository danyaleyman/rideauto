"""Публичный контракт slim/detail v1 (блок F+G). См. docs/API_CONTRACT.md."""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Версии, для которых в репозитории обязаны существовать golden-файлы (CI).
SUPPORTED_API_CONTRACT_FIXTURE_VERSIONS: Tuple[str, ...] = ("v1", "v2")

SLIM_ITEM_V1_REQUIRED_KEYS: FrozenSet[str] = frozenset(
    {
        "id",
        "title",
        "data",
        "read_model",
        "price",
        "price_on_request",
        "year_num",
        "api_contract_version",
    }
)


class CatalogReadModelV1(BaseModel):
    """Поля `read_model` в GET /api/car/{id} (см. build_catalog_read_model)."""

    model_config = ConfigDict(extra="allow")

    mark: str = ""
    model: str = ""
    generation: str = ""
    trim_name: str = ""
    model_group: str = ""
    year: Any = None
    engine_type: str = ""
    transmission_type: str = ""
    drive_type: str = ""
    body_type: str = ""
    color: str = ""
    mileage_km: Any = None
    power_hp: Optional[int] = None
    price_rub: Optional[float] = None
    price_on_request: bool = False
    reserved_placeholder: bool = False
    pricing_tier: str = ""
    customs_included: bool = False
    insurance_cases: Any = None
    damaged_parts_count: Any = None


class SlimCatalogItemV1(BaseModel):
    """Элемент `result[]` в /api/search и /api/similar при list_mode=slim."""

    model_config = ConfigDict(extra="allow")

    id: str
    title: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    read_model: CatalogReadModelV1
    price: Optional[Union[float, int]] = None
    price_on_request: bool = False
    year_num: int = 0
    api_contract_version: str = "v1"
    inner_id: Optional[str] = None
    pricing_tier: Optional[str] = None
    customs_included: Optional[bool] = None
    catalog_created_at: Optional[str] = None
    encar_listing_sold: Optional[bool] = None
    encar_listing_reserved: Optional[bool] = None
    dongchedi_listing_sold: Optional[bool] = None
    catalog_updated_at: Optional[str] = Field(
        default=None,
        description="ISO-время cars.updated_at (свежесть строки каталога). Обязательно при WRA_API_CONTRACT_VERSION=v2.",
    )


class CarDetailResultV1(BaseModel):
    """Объект `result` в GET /api/car/{ref} (до обёртки CarDetailResponse)."""

    model_config = ConfigDict(extra="allow")

    id: str
    # В БД часто `{ "data": { ...карточка… } }`, но встречается и плоский JSON без ключа `data`.
    data: Dict[str, Any] = Field(default_factory=dict)
    read_model: CatalogReadModelV1
    read_model_version: str
    catalog_updated_at: Optional[str] = None

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, v: object) -> object:
        if v is None:
            return v
        return str(v)


class CarDetailEnvelopeV1(BaseModel):
    """Тело ответа GET /api/car/{ref}."""

    model_config = ConfigDict(extra="allow")

    api_version: str = "v1"
    result: CarDetailResultV1


def validate_slim_catalog_item_v1(
    item: Dict[str, Any],
    *,
    require_catalog_updated_at: bool = False,
) -> SlimCatalogItemV1:
    missing = SLIM_ITEM_V1_REQUIRED_KEYS - item.keys()
    if missing:
        raise ValueError(f"slim item missing keys: {sorted(missing)}")
    if require_catalog_updated_at:
        c = item.get("catalog_updated_at")
        if not isinstance(c, str) or not str(c).strip():
            raise ValueError("slim item requires catalog_updated_at (API contract v2)")
    return SlimCatalogItemV1.model_validate(item)


def validate_car_detail_envelope_v1(body: Dict[str, Any]) -> CarDetailEnvelopeV1:
    env = CarDetailEnvelopeV1.model_validate(body)
    if str(body.get("api_version") or "v1").strip().lower() == "v2":
        res = body.get("result")
        if not isinstance(res, dict):
            raise ValueError("detail v2 requires result object")
        c = res.get("catalog_updated_at")
        if not isinstance(c, str) or not str(c).strip():
            raise ValueError("detail v2 requires result.catalog_updated_at")
    return env


class SearchCatalogMetaV1(BaseModel):
    """`meta` в ответе /api/search и /api/cars (slim/full)."""

    model_config = ConfigDict(extra="allow")

    total: int
    limit: int
    per_page: int
    pages: int
    offset: int
    list_mode: str
    api_version: str
    next_cursor: Optional[str] = None
    next_page: Optional[int] = None
    processing_time_ms: Optional[int] = None
    sort: Optional[str] = None


class SimilarCatalogMetaV1(BaseModel):
    model_config = ConfigDict(extra="allow")

    car_id: str
    limit: int
    total_candidates: int = 0
    api_version: str


def validate_catalog_search_response_v1(body: Dict[str, Any]) -> None:
    """Проверка тела ответа поиска после model_dump (slim: полный контракт на элемент)."""
    if not isinstance(body, dict):
        raise ValueError("search body must be a dict")
    meta_raw = body.get("meta")
    if not isinstance(meta_raw, dict):
        raise ValueError("search response missing meta")
    SearchCatalogMetaV1.model_validate(meta_raw)
    api_ver = str(meta_raw.get("api_version") or "v1").strip().lower()
    require_ts = api_ver == "v2"
    mode = str(meta_raw.get("list_mode") or "slim").strip().lower()
    result = body.get("result")
    if not isinstance(result, list):
        raise ValueError("search result must be a list")
    if mode == "slim":
        for i, item in enumerate(result):
            if not isinstance(item, dict):
                raise ValueError(f"search slim item {i} must be a dict")
            validate_slim_catalog_item_v1(item, require_catalog_updated_at=require_ts)
    else:
        for i, item in enumerate(result):
            if not isinstance(item, dict):
                raise ValueError(f"search full row {i} must be a dict")


def validate_catalog_similar_response_v1(body: Dict[str, Any]) -> None:
    if not isinstance(body, dict):
        raise ValueError("similar body must be a dict")
    meta_raw = body.get("meta")
    if not isinstance(meta_raw, dict):
        raise ValueError("similar response missing meta")
    SimilarCatalogMetaV1.model_validate(meta_raw)
    api_ver = str(meta_raw.get("api_version") or "v1").strip().lower()
    require_ts = api_ver == "v2"
    result = body.get("result")
    if not isinstance(result, list):
        raise ValueError("similar result must be a list")
    for i, item in enumerate(result):
        if not isinstance(item, dict):
            raise ValueError(f"similar item {i} must be a dict")
        validate_slim_catalog_item_v1(item, require_catalog_updated_at=require_ts)
