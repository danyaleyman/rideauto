# RideAuto

Сайт-каталог автомобилей из Кореи (Encar), Китая (Che168) и США (Autotrader, ingest в разработке): пользователь ищет машину на сайте, данные подтягиваются с площадок, чистятся и отдаются через API и поиск.

---

## Как устроен проект

```
Площадки (Encar / Che168)
        ↓ скраперы
   PostgreSQL  ← «источник правды» (объявления, цены, статусы)
        ↓ catalog pipeline
   Meilisearch ← быстрый поиск и фильтры
        ↓
   FastAPI (/api/…)
        ↓
   Next.js (web/) ← то, что видит пользователь
```

| Папка | Зачем |
|-------|--------|
| `web/` | Фронтенд (Next.js): каталог, карточка, i18n `/en` и `/ru` |
| `backend/` | API (FastAPI), скраперы, синхронизация каталога |
| `infrastructure/` | Схема Postgres, скрипты Meilisearch |
| `deploy/` | Деплой на сервер: systemd, nginx, скрипты, мониторинг |
| `docs/` | Архитектура, ADR, runbook’и |
| `data/` | Справочники (маппинги марок/моделей и т.п.) |
| `docker-compose.yml` | Локальный стек: Postgres + Redis + Meilisearch + API + web |

**Принцип работы:** скраперы кладут объявления в Postgres → ночной (или ручной) **catalog pipeline** обновляет цены и индекс поиска → сайт ходит в API → API читает Meilisearch (поиск) и Postgres (карточка).

Подробнее: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Быстрый старт (локально)

```bash
# 1) Окружение
cp .env.example .env

# 2) Поднять весь стек
docker compose up -d --build

# 3) Открыть
# Сайт:  http://localhost:3000
# API:   http://localhost:8080/api/health
```

Без Docker (только фронт, если API уже где-то крутится):

```bash
cd web
npm ci
npm run dev
```

---

## Одна команда на сервере

После того как репозиторий лежит в `/opt/rideauto` и настроен `/etc/default/rideauto`:

```bash
sudo bash /opt/rideauto/deploy/scripts/run_full_deploy_pipeline.sh
```

Что делает: `git pull` → обновляет systemd-юниты → права → один цикл скрапа Encar → **catalog pipeline** (цены + Meilisearch) → health-check.

Пропустить этапы при необходимости:

```bash
sudo bash /opt/rideauto/deploy/scripts/run_full_deploy_pipeline.sh \
  --skip-git-pull --skip-daily --skip-postgres-sync --skip-meili-sync --skip-health-check
```

Первичная установка на чистый VPS (nginx + systemd + units):

```bash
chmod +x deploy/deploy_prod.sh
./deploy/deploy_prod.sh
```

---

## Команды по категориям

### Docker (локально)

```bash
docker compose up -d --build          # поднять / пересобрать
docker compose ps                     # статус
docker compose logs -f api web        # логи
docker compose down                   # остановить
```

### Фронтенд (`web/`)

```bash
cd web
npm ci                                # зависимости
npm run dev                           # разработка
npm run build                         # продакшен-сборка
npm run lint                          # линтер
npm run test:unit                     # unit-тесты
```

Из корня репо (e2e / Lighthouse):

```bash
npm ci
npm run test:e2e                      # Playwright (без visual)
npm run test:unit                     # unit web
npm run lint:js                       # eslint web
```

### Backend / API

```bash
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:     .venv\Scripts\activate
pip install -r requirements.txt

uvicorn fastapi_app.main:app --host 0.0.0.0 --port 8080
python -m pytest tests/ -q
```

Полезные точечные тесты:

```bash
cd backend
python -m pytest tests/test_resilience_platform.py tests/test_facet_denylist.py -q
```

### Каталог (Postgres → Meilisearch)

Канон — **один** оркестратор (не вызывайте PG и Meili по отдельности в обычной работе):

```bash
# На сервере
sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_catalog_pipeline_host.sh

# Проверка согласованности PG ↔ Meili
sudo -u rideauto /opt/rideauto/.venv/bin/python \
  /opt/rideauto/backend/scripts/catalog_meili_consistency.py --strict
```

### Скраперы (продакшен)

```bash
# Один цикл Кореи (как в таймере)
sudo -u rideauto /opt/rideauto/deploy/scripts/run_encar_daily_once_prod.sh

# Таймеры
systemctl list-timers --all | grep rideauto
systemctl status rideauto-auto-update.timer rideauto-catalog-pipeline.timer --no-pager

# Диагностика ночных обновлений
bash deploy/scripts/diagnose_nightly_updates.sh
```

Конфиги скраперов: [`scraper_config.yaml`](scraper_config.yaml), [`che168_scraper.yaml`](che168_scraper.yaml), [`autotrader_scraper.yaml`](autotrader_scraper.yaml).  
США (Autotrader): `python backend/autotrader_scraper.py --max-pages 2` (нужна cookie-сессия, см. `docs/research/USA_AUTOTRADER_PIPELINE.md`).
Локальные секреты/лимиты: `*.local.yaml` (в git не попадают).

### Деплой и обслуживание сервера

```bash
# Полный пайплайн (см. выше)
sudo bash /opt/rideauto/deploy/scripts/run_full_deploy_pipeline.sh

# Только обновить код и перезапустить compose/сервисы — см. deploy/DEPLOY.md
# Close-out gate (опционально, когда настраиваете прод)
sudo bash /opt/rideauto/deploy/scripts/prod_closeout_gate.sh

# Clean-read gate (сравнение clean vs legacy)
# DATABASE_URL=... bash deploy/scripts/clean_read_gate.sh
```

### Мониторинг

```bash
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/metrics
systemctl status rideauto-api.service --no-pager
```

Алерты и Grafana: [`docs/MONITORING.md`](docs/MONITORING.md), [`deploy/prometheus/`](deploy/prometheus/).

---

## Что ещё полезно знать

- **Секреты** — только в `.env` / `/etc/default/rideauto`, не в git. Шаблон: [`.env.example`](.env.example), [`deploy/env.rideauto.example`](deploy/env.rideauto.example).
- **Legacy-оркестратор** (`backend/run_system.py` и т.п.) — **не** для продакшена. Только с `WRA_ENABLE_LEGACY_ORCHESTRATION=1` для аварийного восстановления (см. [`backend/SCRAPER_README.md`](backend/SCRAPER_README.md)).
- **Документация глубже:**
  - [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — схема
  - [`docs/CLOSEOUT_REVIEW_2026-10-06.md`](docs/CLOSEOUT_REVIEW_2026-10-06.md) — статус зрелости
  - [`deploy/docs/CATALOG_PIPELINE.md`](deploy/docs/CATALOG_PIPELINE.md) — pipeline каталога
  - [`deploy/DEPLOY.md`](deploy/DEPLOY.md) — деплой
  - [`deploy/docs/CLOUDFLARE.md`](deploy/docs/CLOUDFLARE.md) — Cloudflare
  - [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md) — бэкапы

---

## Лицензия

MIT (если не указано иное в отдельных файлах).
