# Encar production scraper

The script `encar_scraper.py` is a scalable, resumable replacement for the small-sample flow in `parser_full.py`. It is designed to collect up to ~200k listings from encar.com with:

- **Async I/O** (aiohttp): list pages are fetched sequentially; car details are fetched concurrently (configurable limit).
- **Checkpointing**: state is saved in **PostgreSQL** (tables `scraper_checkpoint_state`, `scraper_pending_ids`, …; см. `infrastructure/postgresql/schema.sql`). On restart, the script resumes from the last checkpoint.
- **Storage**: **`storage.backend` must be `postgres`** — записи в таблицу `cars` (нормализованный JSON в `data`) и связанные сущности. DSN: `DATABASE_URL` или `storage.postgres.dsn` в `scraper_config.yaml`.
- **Anti-blocking**: optional proxy list, User-Agent rotation, jitter between requests, exponential backoff and retries (429, 5xx), optional `Retry-After` respect.
- **Configuration**: `scraper_config.yaml` in the repo root; optional **`scraper_config.local.yaml`** in the same folder is merged on top (gitignored). Env overrides `SCRAPER_<section>_<key>` only nest under that section (e.g. `SCRAPER_HTTP_CONCURRENCY=10`).

## Local Postgres (docker-compose)

1. `docker compose up -d postgres` from the repo root (schema loads from `infrastructure/postgresql/schema.sql`).
2. Copy `scraper_config.local.example.yaml` → `scraper_config.local.yaml`, set `storage.postgres.dsn` or rely on `DATABASE_URL`.
3. From PowerShell: `.\backend\scripts\run_encar_local_daily.ps1` (sets `DATABASE_URL` to `127.0.0.1:5432` by default and runs `encar_daily_update.py --once`). Or from `backend/`: `set DATABASE_URL=postgresql://wra:wra@127.0.0.1:5432/wra` and `python encar_daily_update.py --once`.
4. **Смоук (10 машин + один daily-цикл)** без прокси, малые лимиты: `scraper_config.smoke.yaml` (`extends: scraper_config.yaml`). На **Windows + Python 3.13+** к `127.0.0.1:5432` иногда даёт `UnicodeDecodeError` в psycopg2 — используйте контейнер API (Python 3.12): `.\backend\scripts\run_encar_smoke_docker.ps1` после `docker compose up -d postgres`.

## Quick start

1. Install dependencies: `pip install aiohttp PyYAML` (or use project `requirements.txt`).
2. Copy and edit config: `scraper_config.yaml`.
3. Run: `python encar_scraper.py`.

To resume after a stop, run the same command again; it will load pending IDs from the checkpoint and continue.

## Config overview

| Section    | Key examples | Description |
|-----------|--------------|-------------|
| `http`    | `concurrency`, `list_page_size`, `max_list_offset`, `list_page_delay_min/max`, `request_jitter_min/max`, `timeout_total` | Concurrency, pagination, delays, timeouts |
| `retry`   | `max_attempts`, `backoff_base`, `backoff_max`, `retry_statuses` | Retries and backoff |
| `proxy`   | `enabled`, `urls` (HTTP `http://user:pass@host:port`), ротация на каждый запрос | Синхронный `parser_full` читает те же `urls` из `scraper_config.yaml`, либо `ENCAR_PROXY_URLS` |
| `user_agents` | List of strings | Rotated per request |
| `car_types`   | `["for", "kor"]` | Import / domestic |
| `checkpoint`  | `scope`, `max_pending_ids`, `save_interval_seconds` | Checkpoint в Postgres |
| `storage`     | `backend: postgres`, `postgres.dsn`, `store_raw_responses` | Каталог только в Postgres |
| `logging`     | `level`, `file`, `console`, `format` | Log level and outputs |

## Pagination and offset limit

The list API uses `sr: "|ModifiedDate|{offset}|{limit}"`. If the API rejects large offsets (e.g. above 10,000), set `http.max_list_offset` in config. The script stops increasing offset when it gets an error or empty results. A future extension could add date-range or cursor-based strategies (e.g. filter by `ModifiedDate` day-by-day) if the API supports it; the checkpoint already stores the last offset per car type for resume.

## Output

- **PostgreSQL**: таблица `cars` и связанные справочники (см. миграции в `infrastructure/postgresql/`, в т.ч. `007_pricing_recompute_queue.sql`).
- **Цены и tier**: контракт пайплайна и очередь `needs_pricing_recompute` — [`docs/PRICING_PIPELINE.md`](docs/PRICING_PIPELINE.md).

## Опциональный статический дамп

Для `web/public/cars.json` и чанков используйте **`postgres_catalog_sync.py --write-static-json`** (или пайплайн CI).

You can add a small script in the repo that runs this and optionally merges with `parser_full`’s `save_to_file` format.


