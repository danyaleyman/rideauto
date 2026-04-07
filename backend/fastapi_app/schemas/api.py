from __future__ import annotations

from typing import Any, Dict, List, Optional

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


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: List[Dict[str, Any]]
    meta: SearchMeta


class CarDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    result: Dict[str, Any]


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
