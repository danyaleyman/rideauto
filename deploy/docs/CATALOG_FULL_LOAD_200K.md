# Полная загрузка каталога (~200k авто): чеклист и команды

## Готовность

- **Backend:** поиск и фасеты идут через **Meilisearch**; в API выдача **постраничная** (не 200k в одном ответе). Источник истины — **PostgreSQL**; индекс Meili — производная, его можно полностью пересобрать.
- **Frontend:** каталог запрашивает страницы по `per_page`; 200k строк в браузер не грузятся.
- **Условия «да, запускаем полный прогон»:**
  - Применены **все миграции** из `infrastructure/postgresql/migrations/` (включая актуальные `007_*`, `008_*` и т.д.).
  - В Postgres уже лежит полный набор строк `cars` (или вы сначала гоняете импорт/скрейпер — отдельный контур).
  - **Meilisearch:** достаточно RAM под размер индекса (зависит от полей документа в `sync_meilisearch.py`; см. `backend/docs/BLOCK_M_SCALE_COST.md`).
  - Желательно **swap в два UID** (`cars_build` → `cars`), чтобы не портить боевой индекс до успешного окончания.

## 1. Проверки перед заливкой в Meili

На хосте с доступом к Postgres (подставьте DSN):

```bash
cd /opt/rideauto   # корень репозитория
source .venv/bin/activate  # или venv из runbook
export PYTHONPATH=backend
python backend/scripts/meili_sync_preflight.py --dsn "$DATABASE_URL"
```

Если включён **preflight gate** (`WRA_MEILI_PREFLIGHT_GATE=true`), синк не упрётся в «плохие» данные только если пороги выполнены.

## 2. Полная синхронизация Postgres → Meilisearch (рекомендуется blue/green)

В `/etc/default/rideauto` (или экспорт в shell) для **безопасной** публикации:

```bash
export SYNC_PG_DSN='postgresql://USER:PASS@HOST:5432/DB'   # или ваш DATABASE_URL
export WRA_MEILISEARCH_URL='http://127.0.0.1:7700'
export MEILI_MASTER_KEY='…'   # если ключ включён
export WRA_MEILISEARCH_INDEX='cars_build'
export WRA_MEILI_LIVE_INDEX='cars'
export WRA_MEILI_SWAP_INTO_LIVE=1
export MEILISEARCH_SYNC_BATCH=2000   # при необходимости 1000–5000
```

Полная перезаливка **staging-индекса** и **swap** с боевым:

```bash
cd /opt/rideauto
WRA_MEILI_RECREATE_INDEX_ON_SYNC=1 bash deploy/scripts/run_meilisearch_sync_host.sh --recreate-index
```

Эквивалент вручную (если без обёртки):

```bash
python infrastructure/meilisearch/sync_meilisearch.py \
  --pg-dsn "$SYNC_PG_DSN" \
  --meili-url "$WRA_MEILISEARCH_URL" \
  ${MEILI_MASTER_KEY:+--meili-key "$MEILI_MASTER_KEY"} \
  --index-name cars_build \
  --live-index-name cars \
  --swap-into-live \
  --recreate-index \
  --settings infrastructure/meilisearch/index_settings.json \
  --batch-size 2000
```

Только индексация **без** swap (прямая запись в один UID) — для отладки; на проде лучше схема выше.

## 3. Контур «обогащение в Postgres + Meili» (если нужен `postgres_catalog_sync`)

Долго на сотнях тысяч строк; лог в терминал. Из runbook:

```bash
sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_postgres_catalog_sync_host.sh
```

Отключить Meili на этом прогоне (потом отдельно `run_meilisearch_sync_host.sh`):

```bash
sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_postgres_catalog_sync_host.sh --no-meilisearch
```

## 4. После прогона

```bash
curl -sS "http://127.0.0.1:8080/api/health"
curl -sS "http://127.0.0.1:8080/api/search?per_page=1&region=korea&source=encar" | head -c 400
```

Проверьте метрики/логи Meilisearch и API (`/metrics` при включённом `WRA_METRICS_ENABLED`).

## Честное ограничение

«Готовы к 200k» = готовы **при адекватных ресурсах и качестве данных**. Если preflight падает или Meili умирает по OOM — сначала инфраструктура и качество полей в Postgres, а не «ещё один фронтовый коммит».
