# Архитектура Prod Encar (как у крупных агрегаторов)

Цель: быстрый каталог (фильтры и поиск в поисковом движке), SEO за счёт SSR, Postgres как источник правды, кеш и CDN — без SQL-фильтрации каталога в проде.

## Статус миграции (факт по репозиторию)

| Поток | Состояние |
|--------|------------|
| **Vanilla JS → Next.js + SSR** | **Основной каталог в Next.js.** В `web/` — SSR + клиент: маркет Корея/Китай, поиск, фасеты (марка→цвет), диапазоны, сортировка, пагинация (cursor), карточка авто. Легаси `frontend/` остаётся для SEO-лендингов, старых путей и полной карточки Encar (сложный UI), пока не перенесены. |
| **SQLite → PostgreSQL** | **Целевой путь — Postgres:** в `scraper_config.yaml` по умолчанию `storage.backend: postgres` (нужен `DATABASE_URL` или DSN). Для локального режима без Postgres: `SCRAPER_STORAGE_BACKEND=sqlite`. Легаси: `api_server.py`, `catalog_sync_sqlite`, экспорт `cars.json`. |
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
