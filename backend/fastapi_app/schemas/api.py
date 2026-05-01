from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    total: int = Field(description="Оценка Meilisearch (estimatedTotalHits)")
    limit: int
    per_page: int = Field(description="Дубликат limit для совместимости с catalog.js")
    pages: int
    offset: int
    next_cursor: Optional[str] = None
    next_page: Optional[int] = Field(default=None, description="Оставлено для совместимости; при cursor-пагинации часто null")
    processing_time_ms: Optional[int] = None
    list_mode: str = "slim"
    sort: Optional[str] = None
    api_version: str = "v1"


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: List[Dict[str, Any]]
    meta: SearchMeta


class CarDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: Dict[str, Any]
    api_version: str = "v1"


class SimilarMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    car_id: str
    limit: int
    total_candidates: int = 0
    api_version: str = "v1"


class SimilarResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: List[Dict[str, Any]]
    meta: SimilarMeta


class FacetsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    marks: List[Dict[str, Any]] = Field(default_factory=list)
    models: List[Dict[str, Any]] = Field(default_factory=list)
    generations: List[Dict[str, Any]] = Field(default_factory=list)
    trims: List[Dict[str, Any]] = Field(default_factory=list)
    bodies: List[Dict[str, Any]] = Field(default_factory=list)
    fuels: List[Dict[str, Any]] = Field(default_factory=list)
    transmissions: List[Dict[str, Any]] = Field(default_factory=list)
    colors: List[Dict[str, Any]] = Field(default_factory=list)
    api_version: str = "v1"


class CatalogDailyAdditionsResponse(BaseModel):
    """Число строк каталога, созданных сегодня по локальной дате сервера (см. timezone)."""

    count: int = Field(ge=0)
    region: str
    local_date: str = ""
    timezone: str = "Asia/Yekaterinburg"


class WebVitalEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    value: float
    rating: Optional[str] = None
    delta: Optional[float] = None
    navigation_type: Optional[str] = None
    pathname: Optional[str] = None
    user_agent: Optional[str] = None


class CatalogFilterEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str = Field(min_length=1, max_length=128)
    event: str = Field(min_length=1, max_length=128)
    level: Literal["info", "warn", "error"] = "info"
    pathname: Optional[str] = None
    market: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class AuthMagicRequestPayload(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class AuthMagicVerifyPayload(BaseModel):
    token: str = Field(min_length=24, max_length=512)


class AuthSimpleOkResponse(BaseModel):
    ok: bool = True


class AuthUserResponse(BaseModel):
    id: int
    email: str
    is_active: bool = True
    last_login_at: Optional[str] = None


class AuthMeResponse(BaseModel):
    authenticated: bool
    user: Optional[AuthUserResponse] = None
