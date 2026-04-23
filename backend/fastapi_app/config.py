from __future__ import annotations

from functools import lru_cache
import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    pg_dsn: str = Field(
        default="postgresql://postgres:postgres@127.0.0.1:5432/wra",
        description="PostgreSQL DSN (asyncpg), переменная WRA_PG_DSN",
    )
    meilisearch_url: str = Field(default="http://127.0.0.1:7700")
    meilisearch_key: str = Field(default="")
    meilisearch_index: str = Field(default="cars")

    redis_url: Optional[str] = Field(default=None, description="WRA_REDIS_URL — redis://…")
    redis_cache_prefix: str = Field(
        default="wra:api:cache",
        description="Префикс ключей; смена префикса = «мягкая» полная инвалидация без SCAN",
    )
    cache_ttl_search_sec: int = Field(default=10, ge=0, description="Кэш /api/search и /api/cars")
    cache_ttl_facets_sec: int = Field(default=30, ge=0, description="Кэш /api/facets и /api/filters")
    cache_ttl_car_sec: int = Field(default=60, ge=0, description="Кэш /api/car/{id}")

    cache_invalidate_secret: Optional[str] = Field(
        default=None,
        description="Секрет для POST /api/internal/cache/invalidate (заголовок X-WRA-Admin-Key)",
    )

    # --- Image proxy (/api/images/{sha256}) ---
    image_cache_dir: str = Field(
        default="var/image_cache",
        description="Каталог WebP-кэша (относительно cwd или абсолютный путь)",
    )
    image_allowed_hosts: str = Field(
        default="ci.encar.com,imgcar.encar.com,fem.encar.com,www.encar.com",
        description="Список разрешённых хостов для src=, через запятую",
    )
    image_fetch_timeout_sec: float = Field(default=30.0, ge=1.0, le=120.0)
    image_max_fetch_bytes: int = Field(
        default=15_000_000,
        ge=500_000,
        le=80_000_000,
        description="Лимит размера скачиваемого оригинала (байт)",
    )
    image_src_redis_ttl_sec: int = Field(
        default=604800,
        ge=60,
        description="TTL привязки digest→src в Redis (сек)",
    )
    image_encar_referer: str = Field(
        default="https://www.encar.com/",
        description="Referer для запросов к хостам *.encar.com",
    )
    image_response_cache_control: str = Field(
        default="public, max-age=604800, stale-while-revalidate=86400, immutable",
        description="Заголовок Cache-Control для ответа image/webp",
    )

    # --- CDN / edge cache (middleware) ---
    cdn_cc_search: str = Field(
        default="public, max-age=60, stale-while-revalidate=180",
        description="Cache-Control для GET /api/search, /api/cars",
    )
    cdn_cc_facets: str = Field(
        default="public, max-age=120, stale-while-revalidate=86400",
        description="Cache-Control для GET /api/facets, /api/filters",
    )
    cdn_cc_car: str = Field(
        default="public, max-age=60, stale-while-revalidate=300",
        description="Cache-Control для GET /api/car/*",
    )
    cdn_cc_health: str = Field(
        default="public, max-age=30, stale-while-revalidate=120",
        description="Cache-Control для GET /api/health",
    )
    cdn_cc_default_json: str = Field(
        default="public, max-age=30, stale-while-revalidate=120",
        description="Fallback Cache-Control для 304 JSON, если нет специфики пути",
    )
    cdn_etag_enabled: bool = Field(default=True, description="Weak ETag для публичных JSON GET")
    cdn_strip_set_cookie: bool = Field(
        default=True,
        description="Убирать Set-Cookie с публичных GET (/api/search, /api/car, …)",
    )

    metrics_enabled: bool = Field(default=True, description="WRA_METRICS_ENABLED — /metrics и HTTP middleware")
    metrics_path: str = Field(default="/metrics", description="Путь exposition Prometheus")

    # --- Заявки с формы «Как купить» (POST /api/lead) ---
    lead_email_to: str = Field(
        default="danyaleyman@yandex.ru",
        description="WRA_LEAD_EMAIL_TO — куда слать заявки",
    )
    lead_email_from: Optional[str] = Field(
        default=None,
        description="WRA_LEAD_EMAIL_FROM — From (если пусто, берётся WRA_LEAD_SMTP_USER)",
    )
    lead_smtp_host: Optional[str] = Field(
        default=None,
        description="WRA_LEAD_SMTP_HOST — например smtp.yandex.ru",
    )
    lead_smtp_port: int = Field(default=465, ge=1, le=65535, description="WRA_LEAD_SMTP_PORT — 465 SSL или 587 STARTTLS")
    lead_smtp_user: Optional[str] = Field(default=None, description="WRA_LEAD_SMTP_USER")
    lead_smtp_password: Optional[str] = Field(default=None, description="WRA_LEAD_SMTP_PASSWORD")
    lead_smtp_use_tls: bool = Field(
        default=False,
        description="WRA_LEAD_SMTP_USE_TLS=1 — STARTTLS (для порта 587); при 465 оставьте false",
    )

    # --- Runtime translation API (inspection comments etc.) ---
    translate_provider: str = Field(
        default=(os.environ.get("WRA_TRANSLATE_PROVIDER") or "openai"),
        description="WRA_TRANSLATE_PROVIDER: openai | deepseek",
    )
    translate_api_key: str = Field(
        default=(
            os.environ.get("WRA_TRANSLATE_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or ""
        ),
        description="WRA_TRANSLATE_API_KEY (fallback: OPENAI_API_KEY / DEEPSEEK_API_KEY)",
    )
    translate_openai_base_url: str = Field(
        default=(os.environ.get("WRA_TRANSLATE_OPENAI_BASE_URL") or "https://api.openai.com/v1"),
        description="OpenAI chat completions base URL",
    )
    translate_openai_model: str = Field(
        default=(os.environ.get("WRA_TRANSLATE_OPENAI_MODEL") or "gpt-4o-mini"),
        description="OpenAI model for runtime translation",
    )
    translate_deepseek_base_url: str = Field(
        default=(os.environ.get("WRA_TRANSLATE_DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1"),
        description="DeepSeek chat completions base URL",
    )
    translate_deepseek_model: str = Field(
        default=(os.environ.get("WRA_TRANSLATE_DEEPSEEK_MODEL") or "deepseek-chat"),
        description="DeepSeek model for runtime translation",
    )
    translate_timeout_sec: float = Field(
        default=20.0,
        ge=3.0,
        le=90.0,
        description="HTTP timeout for translation API calls",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
