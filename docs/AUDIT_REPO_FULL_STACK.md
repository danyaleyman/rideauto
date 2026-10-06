# Аудит репозитория (полный обзор, не только UI)

Срез **2026-10-06** после Full Maturity Close-out и дожима **10/10** (см. [`CLOSEOUT_REVIEW_2026-10-06.md`](CLOSEOUT_REVIEW_2026-10-06.md)).

## Вердикт: **10/10 (in-repo)**

Цепочка **скрап → Postgres → pricing → Meili → API → Next** закрыта платформенными слоями. Dual-path’ы и «что ударит позже» закрыты ADR/гейтами, не оставлены на удачу.

## Сильные стороны

| Область | Состояние |
|---------|-----------|
| Каталог API | Контракт v1/v2, golden, рантайм-валидация, кэш с эпохой, гидратация Postgres |
| Поиск | Meilisearch, фильтры, сортировки, drift фасетов, denylist YAML, dedupe + `distinctAttribute` |
| Catalog Pipeline | Единственный happy path `run_catalog_pipeline_host.sh` (ADR 0004), lag + consistency |
| Scraper resilience | curl_cffi + Playwright session (ADR 0002); challenge L0–L3 (ADR 0005) |
| Clean read | Compose defaults MODE=1 / 100% / fallbacks off; `clean_read_gate.sh` |
| Наблюдаемость | Prometheus (SLO + ops), job textfile, Grafana JSON, outbox backlog alert |
| Scale | `deploy/docs/SCALE.md` Tier 0–2 ladder |
| PD / edge | `pd_retention_purge`, Cloudflare runbook |
| i18n | `/en` `/ru` middleware rewrite + hreflang |
| Безопасность процессов | Gitleaks в CI, секреты через env |

## Остатки (не архитектурные дыры)

### Операционные

- **Прод attestation:** fire-drill Alertmanager, CF checklist, China dates, 14-day clean soak — шаблоны есть.
- **OTEL на проде:** staging-first (ADR 0003).

### Данные / продукт

- Группы с ключом `id:` (не VIN / не source) — в JSONL-отчёте auto-apply, не auto-link (осознанно).
- **estimatedTotalHits** — QA на проде после settings change.
- Pixel / Storybook / virtualized lists — P2 polish.

## Вывод

**Архитектура и процессы в репозитории — 10/10** по критерию Done проекта. Включение timers/CF/Slack на живом хосте — ops follow-up, не открытая дыра (см. close-out review).
