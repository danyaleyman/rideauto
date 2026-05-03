"""
Prometheus metrics (prometheus_client).

Несколько воркеров uvicorn: задайте ``PROMETHEUS_MULTIPROC_DIR`` и подключите
``MultiProcessCollector`` при сборе метрик (см. документацию prometheus_client).

Метрики:
- ``wra_http_request_duration_seconds`` — histogram latency
- ``wra_http_response_body_bytes`` — histogram размера тела (если известен; streaming может не попадать)
- ``wra_http_requests_total`` — counter (method, path_group, status_class)
- ``wra_cache_lookups_total`` — counter (segment, result=hit|miss); enrich: ``catalog_enrich_pair_redis``, ``catalog_enrich_pg_batch``
- ``wra_catalog_enrich_llm_calls_total`` — LLM enrich (phase)
- ``wra_catalog_enrich_llm_http_seconds`` — время HTTP к OpenAI (batched запрос)
"""
from __future__ import annotations

import re
from typing import Final

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

_RE_CAR_ID: Final = re.compile(r"^/api/car/[^/]+$")
_RE_IMAGE_ID: Final = re.compile(r"^/api/images/[^/]+")

HTTP_REQUEST_DURATION: Final = Histogram(
    "http_request_duration_seconds",
    "Длительность HTTP-запроса (сек)",
    ("method", "path_group"),
    namespace="wra",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0, float("inf")),
)

HTTP_REQUESTS: Final = Counter(
    "http_requests_total",
    "Число HTTP-запросов",
    ("method", "path_group", "status_class"),
    namespace="wra",
)

HTTP_RESPONSE_BODY_BYTES: Final = Histogram(
    "http_response_body_bytes",
    "Размер тела ответа (байт), если доступен буфер (не streaming)",
    ("method", "path_group"),
    namespace="wra",
    buckets=(256.0, 1024.0, 4096.0, 16384.0, 65536.0, 262144.0, 1048576.0, 4194304.0, float("inf")),
)

CACHE_LOOKUPS: Final = Counter(
    "cache_lookups_total",
    "Проверки Redis JSON-кэша каталога",
    ("segment", "result"),
    namespace="wra",
)

CATALOG_ENRICH_LLM_PHASE: Final = Counter(
    "catalog_enrich_llm_calls_total",
    "Вызовы LLM-дозаполнения каталога (по фазе)",
    ("phase",),
    namespace="wra",
)

CATALOG_ENRICH_LLM_HTTP_SECONDS: Final = Histogram(
    "catalog_enrich_llm_http_seconds",
    "Длительность POST chat completions при catalog enrich LLM",
    namespace="wra",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 15.0, 45.0, float("inf")),
)


def normalize_path_group(path: str) -> str:
    """Низкая кардинальность для label path_group."""
    path = (path or "").split("?", 1)[0]
    if not path:
        return "/"
    if path == "/metrics":
        return "/metrics"
    if _RE_CAR_ID.match(path):
        return "/api/car/{id}"
    if _RE_IMAGE_ID.match(path):
        return "/api/images/{image_id}"
    if path.startswith("/api/internal/"):
        return "/api/internal/..."
    if path.rstrip("/") == "/api/catalog/enrich-terms":
        return "/api/catalog/enrich-terms"
    if path.rstrip("/") == "/api/internal/catalog/enrich-terms":
        return "/api/internal/catalog/enrich-terms"
    return path


def _status_class(code: int) -> str:
    if code >= 500:
        return "5xx"
    if code >= 400:
        return "4xx"
    if code >= 300:
        return "3xx"
    if code >= 200:
        return "2xx"
    return "other"


def observe_http(method: str, path_group: str, status_code: int, duration_sec: float) -> None:
    method_u = (method or "UNKNOWN").upper()
    HTTP_REQUEST_DURATION.labels(method_u, path_group).observe(max(duration_sec, 0.0))
    HTTP_REQUESTS.labels(method_u, path_group, _status_class(int(status_code))).inc()


def observe_http_response_body_bytes(method: str, path_group: str, nbytes: int) -> None:
    if nbytes <= 0:
        return
    method_u = (method or "UNKNOWN").upper()
    HTTP_RESPONSE_BODY_BYTES.labels(method_u, path_group).observe(float(nbytes))


def inc_cache_lookup(segment: str, *, hit: bool) -> None:
    seg = (segment or "unknown").strip() or "unknown"
    CACHE_LOOKUPS.labels(seg, "hit" if hit else "miss").inc()


def inc_catalog_enrich_llm_phase(phase: str) -> None:
    lab = (phase or "unknown").strip() or "unknown"
    CATALOG_ENRICH_LLM_PHASE.labels(lab).inc()


def observe_catalog_enrich_llm_http(duration_sec: float) -> None:
    CATALOG_ENRICH_LLM_HTTP_SECONDS.observe(max(duration_sec, 0.0))


def metrics_payload() -> tuple[bytes, str]:
    """Тело ответа /metrics и Content-Type."""
    return generate_latest(), CONTENT_TYPE_LATEST
