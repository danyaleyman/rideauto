# Архитектура Prod Encar (как у крупных агрегаторов)

Цель: быстрый каталог (фильтры и поиск в поисковом движке), SEO за счёт SSR, Postgres как источник правды, кеш и CDN — без SQL-фильтрации каталога в проде.

## Статус миграции (факт по репозиторию)

| Поток | Состояние |
|--------|------------|
| **Vanilla JS → Next.js + SSR** | **Частично.** В `web/` — Next.js (SSR): главная, список каталога, страница авто. Полный UX каталога (фильтры, китайский рынок, поведение как в легаси) пока в `frontend/` + `catalog.js` / `car-page.js`. |
| **SQLite → PostgreSQL** | **В стеке Docker — да:** Postgres + FastAPI. **Легаси сохраняется:** `api_server.py` (SQLite), экспорт `cars.json`, `catalog_sync_sqlite` в `auto_update`, в `scraper_config.yaml` по умолчанию `storage.backend: sqlite`. |
| **Схема ниже** | Реализуется, если трафик идёт на FastAPI + Meilisearch + Postgres, скрапер пишет в **Postgres** (`storage.backend: postgres` + DSN), после импорта запускается **sync Meilisearch**. |
| **Cloudflare** | Заголовки кеша в FastAPI есть; проксирование в зоне CF — вне репозитория. |

## Поток данных (целевой production)

```text
[ Next.js — SSR + SPA после гидратации ]
              │
              ▼
[ FastAPI — тонкий API-слой ]
              │
     ┌────────┴────────┐
     ▼                 ▼
[ Meilisearch ]   [ PostgreSQL ]
поиск, facets,     полные карточки,
сортировка         пользователи, связи
```

- **Каталог (список)**: запрос → FastAPI → **Meilisearch** (ids + total) → **Postgres** только `WHERE car_id = ANY($ids)` для гидратации JSON-карточек. Фильтры в SQL по полям каталога **не** строятся.
- **Карточка авто**: FastAPI → Postgres по id / inner_id (точечное чтение, не «поиск каталога»).
- **Redis**: JSON-кеш ответов search / facets / car (см. `fastapi_app.cached_route` и TTL в настройках).
- **CDN (например Cloudflare)**: статика фронта, кешируемые GET API, изображения; заголовки для кеша — middleware CDN в FastAPI.

## Пайплайн данных

```text
Scraper → PostgreSQL → синхронизация индекса Meilisearch (отдельный job / cron)
```

Скрапер **сам** Meilisearch не обновляет: после импорта в Postgres нужно запускать синхронизацию индекса (см. `infrastructure/meilisearch/sync_meilisearch.py` и настройки индекса). Чекпоинт скрапера по умолчанию — отдельный файл SQLite (`checkpoint.path`), это нормально и не отменяет хранение машин в Postgres.

## Сервисы в репозитории

| Слой        | Компонент   | Путь / сервис |
|------------|-------------|----------------|
| Frontend   | Next.js     | `web/` (SSR), legacy — `frontend/` |
| API        | FastAPI     | `backend/fastapi_app`, Docker `api` |
| Search     | Meilisearch | Docker `meilisearch` |
| DB         | PostgreSQL  | Docker `postgres` |
| Cache      | Redis       | Docker `redis` |

## Правило продакшена

**Не** реализовывать фильтрацию и полнотекст каталога через SQL (ни SQLite `api_server`, ни тяжёлые `WHERE` по JSON в Postgres для листинга). Исключение — выборка по списку id после Meilisearch и точечные чтения карточки.
