# RideAuto Web (Next.js)

SSR каталога, карточка авто, фильтры Meilisearch. См. [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Локальная разработка

```bash
cd web
npm ci
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000). API: rewrites на `WRA_API_INTERNAL` (по умолчанию `http://127.0.0.1:8080`).

## Feature flags (build-time)

Переменные `NEXT_PUBLIC_*` вшиваются при `next build` / `docker compose build web`.

| Переменная | Значение | Эффект |
|------------|----------|--------|
| `NEXT_PUBLIC_FEATURE_VIRTUAL_LIST` | `1` | Виртуализация списка каталога (`@tanstack/react-virtual`) |
| `NEXT_PUBLIC_FEATURE_HOME_TRUST` | `0` | Скрыть блок доверия на главной |
| `NEXT_PUBLIC_SENTRY_DSN` | URL | Клиентские ошибки в Sentry |
| `NEXT_PUBLIC_CSP_ENFORCE` | `1` | CSP enforce вместо report-only |
| `WRA_ISR_WARM_CAR_REFS` | `id1,id2` | Пререндер карточек при `WRA_ISR_WARM_STATIC_BUILD=1` (не в Docker build) |

### Тест виртуального списка локально

```bash
# PowerShell
$env:NEXT_PUBLIC_FEATURE_VIRTUAL_LIST="1"
npm run dev

# bash
NEXT_PUBLIC_FEATURE_VIRTUAL_LIST=1 npm run dev
```

E2E smoke для virtual scroll (мок API):

```bash
npm run test:e2e -- --grep @virtual-scroll
```

## OpenAPI-клиент

```bash
npm run generate:api-types   # src/lib/generated/openapi.ts
```

Типизированные запросы: `src/lib/openapi-fetch-client.ts` (`openapi-fetch`). Каталог в UI ходит на `/api/search` (alias), в OpenAPI — `GET /api/cars`.

## Тесты и качество

```bash
npm run test:unit
npm run lint
npm run check:budget   # после npm run build
```

Корневой репозиторий: `npm run test:e2e`, `npm run test:e2e:a11y` (axe), `npm run test:e2e:staging` (реальный `https://rideauto.ru`).

Пороги JS: `bundle-budget.json` + `scripts/check-bundle-budget.mjs` (CI в `next-build`). Доступность: [`docs/A11Y.md`](docs/A11Y.md).

## Docker (prod)

См. [`deploy/DEPLOY.md`](../deploy/DEPLOY.md). После правок `.env`:

```bash
docker compose build web
docker compose up -d web
```
