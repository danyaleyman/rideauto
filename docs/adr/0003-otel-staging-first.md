# ADR 0003: OpenTelemetry on staging first

- **Статус:** принято  
- **Дата:** 2026-10-06  

## Контекст

Full Maturity Close-out требует tracing hot path (search → Meili/PG). OTEL уже в коде (`WRA_OTEL_*`), но без обязательного прод-collector.

## Решение

1. **Staging:** `WRA_OTEL_ENABLED=1` + OTLP endpoint (Jaeger/Tempo/Collector).
2. **Production:** включать только при наличии endpoint и sample rate; иначе staging-only до отдельного ops ticket.
3. Не блокировать close-out отсутствием Jaeger в docker-compose репозитория.

## Последствия

- Fire-drill и SLO алерты остаются первичным prod gate.
- Документировать endpoint в `/etc/default/rideauto` при включении.
