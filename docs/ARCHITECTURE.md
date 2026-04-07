# Архитектура Prod Encar (как у крупных агрегаторов)

Цель: быстрый каталог (фильтры и поиск в поисковом движке), SEO за счёт SSR, Postgres как источник правды, кеш и CDN — без SQL-фильтрации каталога в проде.

## Поток данных

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
Scraper → PostgreSQL → синхронизация индекса Meilisearch
```

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
