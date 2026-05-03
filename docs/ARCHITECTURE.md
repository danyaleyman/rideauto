# Архитектура RideAuto (как у крупных агрегаторов)

Цель: быстрый каталог (фильтры и поиск в поисковом движке), SEO за счёт SSR, Postgres как источник правды, кеш и CDN — без SQL-фильтрации каталога в проде.

## Статус миграции (факт по репозиторию)

| Поток | Состояние |
|--------|------------|
| **Фронт** | **Next.js в `web/`** — SSR + клиент: маркет Корея/Китай, поиск, фасеты, карточка. Статические SEO-лендинги генерируются в `web/public/seo/`. |
| **Хранилище** | **Каталог и чекпоинт скрапера — Postgres** (`storage.backend: postgres`, DSN). |
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

## Слои данных в каталоге (внутренний контракт)

Единая терминология raw → `cars.data` → `*_clean` → read model / Meilisearch — в **`backend/docs/BLOCK_0_SINGLE_SOURCE_OF_TRUTH.md`**. Поэтапное включение clean read (флаги, dual-run, откат): **`backend/docs/BLOCK_D_CLEAN_ROLLOUT.md`**.

## Пайплайн данных

```text
Scraper → PostgreSQL → синхронизация индекса Meilisearch (отдельный job / cron)
```

Скрапер **сам** Meilisearch не обновляет: после импорта в Postgres нужно запускать синхронизацию индекса (см. `infrastructure/meilisearch/sync_meilisearch.py` и настройки индекса). Состояние чекпоинта скрапера хранится в Postgres (`scraper_checkpoint_state`, `scraper_pending_ids`, … в `infrastructure/postgresql/schema.sql`).

## Сервисы в репозитории

| Слой        | Компонент   | Путь / сервис |
|------------|-------------|----------------|
| Frontend   | Next.js     | `web/` |
| API        | FastAPI     | `backend/fastapi_app`, Docker `api` |
| Search     | Meilisearch | Docker `meilisearch` |
| DB         | PostgreSQL  | Docker `postgres` |
| Cache      | Redis       | Docker `redis` |

## Правило продакшена

**Не** строить фильтрацию и полнотекст листинга тяжёлыми `WHERE` по JSON в Postgres. Исключение — выборка по списку id после Meilisearch и точечные чтения карточки.

