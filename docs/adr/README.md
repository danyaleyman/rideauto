# Architecture Decision Records (ADR)

Короткие записи о нетривиальных решениях. Формат: `NNNN-title.md`.

## Индекс

| ADR | Решение |
|-----|---------|
| [0001](0001-use-adr-for-meilisearch-schema.md) | Использовать ADR для спорных изменений схемы Meilisearch |
| [0002](0002-scraper-resilience-hybrid.md) | Hybrid scrape resilience: curl_cffi + Playwright session, не SeleniumBase |
| [0003](0003-otel-staging-first.md) | OpenTelemetry сначала на staging |
| [0004](0004-canonical-catalog-entrypoints.md) | Один happy path catalog pipeline; outbox = инкремент |
| [0005](0005-challenge-escalation.md) | Challenge L0–L3 без CAPTCHA farms |

## Когда писать ADR

- Меняется `distinctAttribute`, набор filterable полей или семантика дедупа в индексе.
- Ломающее изменение публичного API (контракт v2+).
- Отказ от Redis-кэша или смена источника истины для цен/листингов.
