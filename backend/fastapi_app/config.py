from __future__ import annotations

from functools import lru_cache
import os
from typing import Optional

from pydantic import Field, field_validator
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

    @field_validator("meilisearch_key", mode="before")
    @classmethod
    def _strip_meilisearch_key(cls, v: object) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        return s if s else ""
    clean_read_mode: bool = Field(
        default=False,
        description="WRA_CLEAN_READ_MODE — prefer *_clean blocks in runtime reads",
    )
    clean_read_percent: int = Field(
        default=100,
        ge=0,
        le=100,
        description="WRA_CLEAN_READ_PERCENT — rollout share for clean reads",
    )
    legacy_fallbacks_enabled: bool = Field(
        default=True,
        description="WRA_LEGACY_FALLBACKS_ENABLED — allow fallback to legacy fields",
    )
    api_contract_version: str = Field(
        default="v1",
        description="WRA_API_CONTRACT_VERSION — API contract version label",
    )

    redis_url: Optional[str] = Field(default=None, description="WRA_REDIS_URL — redis://…")
    redis_cache_prefix: str = Field(
        default="wra:api:cache",
        description="Префикс ключей; смена префикса = «мягкая» полная инвалидация без SCAN",
    )
    cache_ttl_search_sec: int = Field(default=10, ge=0, description="Кэш /api/search и /api/cars")
    cache_ttl_facets_sec: int = Field(default=30, ge=0, description="Кэш /api/facets и /api/filters")
    cache_ttl_car_sec: int = Field(default=60, ge=0, description="Кэш /api/car/{id}")

    catalog_cache_epoch: str = Field(
        default="",
        max_length=128,
        description=(
            "WRA_CATALOG_CACHE_EPOCH — произвольная метка (например дата релиза). "
            "Меняется → другой ключ Redis для search/similar/car/facets при тех же query."
        ),
    )

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
    metrics_response_body_bytes_enabled: bool = Field(
        default=True,
        description="WRA_METRICS_RESPONSE_BODY_BYTES — histogram размера тела ответа, если body уже материализован",
    )

    rate_limit_public_per_minute: int = Field(
        default=0,
        ge=0,
        description="WRA_RATE_LIMIT_PUBLIC_PER_MINUTE — лимит GET /api/search|/cars|/facets|/filters на IP (0=выкл); для нескольких воркеров задайте WRA_RATE_LIMIT_REDIS_URI",
    )
    rate_limit_trust_forwarded_for: bool = Field(
        default=False,
        description="WRA_RATE_LIMIT_TRUST_FORWARDED_FOR — брать клиента из X-Forwarded-For (только за доверенным прокси!)",
    )
    rate_limit_redis_uri: Optional[str] = Field(
        default=None,
        description="WRA_RATE_LIMIT_REDIS_URI — отдельный Redis для slowapi; если пусто, при наличии WRA_REDIS_URL он же используется как storage лимита (нужно при uvicorn --workers >1)",
    )

    otel_enabled: bool = Field(default=False, description="WRA_OTEL_ENABLED — OpenTelemetry OTLP HTTP для FastAPI")
    otel_service_name: str = Field(default="rideauto-api", description="WRA_OTEL_SERVICE_NAME")
    otel_exporter_otlp_traces_endpoint: Optional[str] = Field(
        default=None,
        description="WRA_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT — например http://jaeger:4318/v1/traces",
    )

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

    # --- Email magic link auth ---
    auth_enabled: bool = Field(default=True, description="WRA_AUTH_ENABLED — включить auth API")
    auth_secret: str = Field(
        default="",
        description="WRA_AUTH_SECRET — секрет для хэширования токенов/сессий (обязателен в проде)",
    )
    auth_cookie_name: str = Field(default="wra_session", description="WRA_AUTH_COOKIE_NAME")
    auth_cookie_secure: bool = Field(
        default=True,
        description="WRA_AUTH_COOKIE_SECURE=1 для HTTPS-only cookie",
    )
    auth_magic_ttl_min: int = Field(default=20, ge=5, le=120, description="WRA_AUTH_MAGIC_TTL_MIN")
    auth_session_ttl_hours: int = Field(default=24 * 30, ge=1, le=24 * 365, description="WRA_AUTH_SESSION_TTL_HOURS")
    auth_magic_link_base_url: str = Field(
        default="https://rideauto.ru",
        description="WRA_AUTH_MAGIC_LINK_BASE_URL — базовый URL для ссылки в письме",
    )
    auth_rate_limit_per_ip_hour: int = Field(default=40, ge=1, le=500)
    auth_rate_limit_per_email_hour: int = Field(default=10, ge=1, le=100)

    auth_smtp_host: Optional[str] = Field(
        default=None,
        description="WRA_AUTH_SMTP_HOST — например smtp.yandex.ru",
    )
    auth_smtp_port: int = Field(default=465, ge=1, le=65535)
    auth_smtp_user: Optional[str] = Field(default=None)
    auth_smtp_password: Optional[str] = Field(default=None)
    auth_smtp_use_tls: bool = Field(default=False, description="STARTTLS для 587")
    auth_email_from: Optional[str] = Field(
        default=None,
        description="WRA_AUTH_EMAIL_FROM — From, если пусто используется auth smtp user",
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

    catalog_enrich_enabled: bool = Field(
        default=True,
        description="WRA_CATALOG_ENRICH_ENABLED — включить POST /api/catalog/enrich-terms (статическое KO→RU/EN)",
    )
    catalog_enrich_secret: Optional[str] = Field(
        default=None,
        description="WRA_CATALOG_ENRICH_SECRET — если задан: заголовок X-WRA-Catalog-Enrich-Key должен совпадать",
    )
    catalog_enrich_llm_fallback: bool = Field(
        default=False,
        description="WRA_CATALOG_ENRICH_LLM_FALLBACK — разрешить дозаполнение пустого RU через OpenAI (без БД)",
    )
    catalog_enrich_llm_max_items: int = Field(
        default=12,
        ge=1,
        le=24,
        description="WRA_CATALOG_ENRICH_LLM_MAX_ITEMS — макс. позиций за один batched LLM-запрос",
    )
    catalog_enrich_openai_model: str = Field(
        default="gpt-4o-mini",
        description="WRA_CATALOG_ENRICH_OPENAI_MODEL — модель для enrich-fallback (пусто в env = default)",
    )
    catalog_enrich_max_payload_chars: int = Field(
        default=96_000,
        ge=512,
        le=512_000,
        description="WRA_CATALOG_ENRICH_MAX_PAYLOAD_CHARS — сумма len(text) по items (анти‑злоупотребление)",
    )
    catalog_enrich_rate_limit_per_minute: int = Field(
        default=0,
        ge=0,
        le=100_000,
        description="WRA_CATALOG_ENRICH_RATE_LIMIT_PER_MINUTE — 0 выкл.; иначе лимит POST/мин по IP или по enrich‑ключу",
    )
    catalog_enrich_pair_redis_ttl_sec: int = Field(
        default=2_592_000,
        ge=3_600,
        le=31_536_000,
        description="TTL для Redis KV пары text+domain→RU/EN (по умолчанию ~30 сут)",
    )
    catalog_enrich_llm_retry_attempts: int = Field(
        default=3,
        ge=1,
        le=8,
        description="WRA_CATALOG_ENRICH_LLM_RETRY_ATTEMPTS — попытки HTTP к OpenAI (429/502/503/504 + сеть)",
    )
    catalog_enrich_llm_retry_base_delay_sec: float = Field(
        default=0.45,
        ge=0.05,
        le=15.0,
        description="WRA_CATALOG_ENRICH_LLM_RETRY_BASE_DELAY_SEC — пауза перед повтором, экспонента x2 capped",
    )
    catalog_enrich_pg_cache_enabled: bool = Field(
        default=False,
        description="WRA_CATALOG_ENRICH_PG_CACHE_ENABLED — разрешить read-only чтение term_translation_cache в enrich",
    )
    catalog_enrich_pg_timeout_sec: float = Field(
        default=2.5,
        ge=0.3,
        le=30.0,
        description="WRA_CATALOG_ENRICH_PG_TIMEOUT_SEC — таймаут батч-запроса к term_translation_cache",
    )
    catalog_enrich_pg_max_keys: int = Field(
        default=288,
        ge=8,
        le=2000,
        description="WRA_CATALOG_ENRICH_PG_MAX_KEYS — макс. пар ключей в одном SELECT (UNNEST)",
    )
    catalog_enrich_pg_max_rounds: int = Field(
        default=8,
        ge=1,
        le=48,
        description="WRA_CATALOG_ENRICH_PG_MAX_ROUNDS — доп. раунды UNNEST, пока не исчерпаны ключи",
    )
    catalog_enrich_etag_revision: str = Field(
        default="1",
        max_length=64,
        description="WRA_CATALOG_ENRICH_ETAG_REVISION — смена bust кэша ETag при обновлении статических словарей",
    )
    catalog_enrich_internal_llm_fallback: bool = Field(
        default=False,
        description="WRA_CATALOG_ENRICH_INTERNAL_LLM_FALLBACK — для POST /internal/... включать LLM (если и глобальный LLM вкл.)",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
