"""Опциональный OpenTelemetry для FastAPI (WRA_OTEL_ENABLED=1)."""

from __future__ import annotations

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def init_otel_instrumentation(app: FastAPI) -> None:
    from fastapi_app.config import get_settings

    s = get_settings()
    if not s.otel_enabled:
        return
    endpoint = (s.otel_exporter_otlp_traces_endpoint or "").strip()
    if not endpoint:
        endpoint = "http://127.0.0.1:4318/v1/traces"
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as e:
        logger.warning("OpenTelemetry packages missing, skip tracing: %s", e)
        return

    resource = Resource.create(
        {
            "service.name": (s.otel_service_name or "rideauto-api").strip() or "rideauto-api",
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry tracing enabled endpoint=%s", endpoint)
