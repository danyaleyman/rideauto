# RideAuto — справочник команд (локально и сервер)

> **Назначение:** шпаргалка для DevOps и разработки. Файл в репозитории — **не** деплоится как часть приложения; храните копию у себя.  
> **Секреты:** реальные пароли и ключи **не** вставляйте в этот файл — только плейсхолдеры вида `{{...}}`.

---

## Оглавление

1. [🏠 Локальные команды (ПК, Windows)](#-локальные-команды-пк-windows)  
2. [🖥️ Подключение к серверу](#️-подключение-к-серверу)  
3. [🐳 Docker](#-docker)  
4. [📦 Git](#-git)  
5. [🔄 Синхронизация данных (PostgreSQL, Meilisearch)](#-синхронизация-данных-postgresql-meilisearch)  
6. [🧹 Очистка кэша](#-очистка-кэша)  
7. [🔍 Диагностика и логи](#-диагностика-и-логи)  
8. [🚀 Скрипты деплоя](#-скрипты-деплоя)  
9. [❌ Частые ошибки](#-частые-ошибки)  
10. [🔧 Полезные однострочники](#-полезные-однострочники)  
11. [⚡ Быстрые комбо](#-быстрые-комбо)  
12. [Как добавить свою команду в этот файл](#как-добавить-свою-команду-в-этот-файл)

**Условные обозначения**

- ✨ — особенно часто нужная команда  
- ⚠️ — опасная или необратимая операция  

**Контекст (подставьте свои значения):**

| Что | Значение в вашем проекте |
|-----|---------------------------|
| Сервер | `root@62.76.31.51` (или ваш SSH-alias) |
| Каталог на сервере | `/opt/rideauto` |
| Git remote «сервер» | `server` → обычно `62.76.31.51:git/rideauto.git` |
| Compose-сервисы | `postgres`, `redis`, `meilisearch`, `api`, `web` |
| Systemd API (если API **не** в Docker) | `rideauto-api.service` |

---

## 🏠 Локальные команды (ПК, Windows)

### Открыть проект и проверить ветку

```powershell
Set-Location "C:\Users\<ВЫ>\...\rideauto"
git status
git branch -v
```

**Что делает:** показывает состояние репозитория и текущую ветку.  
**Когда:** перед коммитом, после переключения веток.

---

### Запуск линтера фронта

```powershell
Set-Location "...\rideauto\web"
npm run lint
```

**Что делает:** ESLint для Next.js.  
**Когда:** перед коммитом изменений в `web/`.

---

### Запуск тестов backend (пример)

```powershell
Set-Location "...\rideauto\backend"
python -m pytest tests/ -q
```

**Что делает:** прогон unit-тестов Python.  
**Когда:** после правок в `backend/`.

---

### Push на GitHub (`origin`)

```powershell
Set-Location "...\rideauto"
git push origin main
```

**Что делает:** отправляет коммиты на `origin`.  
**Когда:** публикация в GitHub.

---

### Push на свой сервер (remote `server`)

```powershell
git push server main
```

**Что делает:** пушит ветку `main` на bare-репозиторий на сервере.  
**Когда:** деплой через git на `62.76.31.51`.  
**Примечание:** нужен настроенный SSH-ключ или интерактивный ввод пароля.

---

## 🖥️ Подключение к серверу

### SSH под root

```bash
ssh root@62.76.31.51
```

**Что делает:** интерактивная сессия на сервере.  
**Когда:** любые административные задачи.

✨ **Рекомендация:** завести SSH-config alias:

```text
# ~/.ssh/config (на ПК)
Host rideauto-prod
    HostName 62.76.31.51
    User root
    IdentityFile ~/.ssh/id_ed25519
```

Затем: `ssh rideauto-prod`

---

### Перейти в каталог проекта на сервере

```bash
cd /opt/rideauto
```

**Что делает:** корень монорепозитория на проде.

---

## 🐳 Docker

> Имена контейнеров могут быть `rideauto-api-1`, `rideauto-postgres-1` и т.д. — зависят от имени каталога и проекта Compose. Уточняйте через `docker compose ps`.

### Список сервисов и статус

```bash
cd /opt/rideauto
docker compose ps
```

**Что делает:** какие контейнеры запущены, порты, health.  
**Когда:** первая диагностика «что живо».

✨

---

### Логи API и web (follow)

```bash
cd /opt/rideauto
docker compose logs -f api web
```

**Что делает:** поток логов FastAPI и Next.js.  
**Когда:** отладка 500, таймаутов, после деплоя.

✨

---

### Пересобрать и поднять API после правок backend

```bash
cd /opt/rideauto
git pull
docker compose build api
docker compose up -d api
```

**Что делает:** новый образ `api`, перезапуск контейнера.  
**Когда:** изменился код в `backend/` или зависимости Dockerfile.

⚠️ Кратковременный рестарт API; при необходимости обновите и `web`.

---

### Пересобрать web

```bash
cd /opt/rideauto
docker compose build web
docker compose up -d web
```

**Что делает:** новый фронт.  
**Когда:** изменения в `web/`.

---

### Зайти в контейнер Postgres (psql)

```bash
cd /opt/rideauto
docker compose exec postgres psql -U wra -d wra
```

**Что делает:** интерактивный psql (пользователь/БД по умолчанию из `docker-compose.yml`; у вас могут отличаться — смотрите `.env`).

**Когда:** ручные SQL-запросы, проверка счётчиков.

---

### Зайти в shell контейнера API

```bash
cd /opt/rideauto
docker compose exec api sh
```

**Что делает:** оболочка внутри образа API.  
**Когда:** отладка путей, ручной `python -c ...`.

---

## 📦 Git

### На сервере: обновить рабочую копию из remote

Зависит от того, как у вас устроен деплой: `git pull` из обычного репо или `git --work-tree=/opt/rideauto checkout` из bare. Типичный вариант:

```bash
cd /opt/rideauto
git pull origin main
# или: git pull server main
```

**Что делает:** подтягивает коммиты.  
**Когда:** после пуша с ПК на тот же remote, с которого тянет сервер.

---

### Локально: коммит и пуш на сервер

```powershell
git add -A
git commit -m "описание"
git push server main
```

**Что делает:** отправка на `server`.  
**Когда:** вы ведёте прод с bare на 62.76.31.51.

---

## 🔄 Синхронизация данных (PostgreSQL, Meilisearch)

### Meilisearch: полный синк с хоста ✨

```bash
sudo bash /opt/rideauto/deploy/scripts/run_meilisearch_sync_host.sh
```

**Что делает:** читает строки из PostgreSQL (`cars`) и заливает в индекс Meilisearch (настройки из `/etc/default/rideauto`: `SYNC_PG_DSN`, `WRA_MEILISEARCH_URL`, ключ, опции swap/recreate).  
**Когда:** «поиск не видит новые машины», после большого импорта, восстановление индекса.

**Переменные:** см. `deploy/docs/CATALOG_FULL_LOAD_200K.md`, `deploy/docs/RUNBOOK_OPERATIONS.md`.

---

### Meilisearch: пересоздать индекс (осторожно)

```bash
WRA_MEILI_RECREATE_INDEX_ON_SYNC=1 sudo bash /opt/rideauto/deploy/scripts/run_meilisearch_sync_host.sh --recreate-index
```

**Что делает:** пересборка индекса с нуля (если так настроены env).  
**Когда:** повреждённый индекс, смена схемы.

⚠️ Нагрузка на Meili и Postgres; на проде лучше окно обслуживания и схема staging+swap.

---

### PostgreSQL: обогащение каталога + опционально Meili ✨

```bash
sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_postgres_catalog_sync_host.sh
```

**Что делает:** `postgres_catalog_sync.py` (цены, локализация, upsert логика) из хостового venv; DSN из `/etc/default/rideauto`.  
**Когда:** после скрейпера, если нужно прогнать каталог без полного перезапуска пайплайна.

---

### PostgreSQL: только скрейпер Che168 и встроенный sync (если запускаете скрейпер сами)

```bash
cd /opt/rideauto
export DATABASE_URL='postgresql://{{USER}}:{{PASSWORD}}@127.0.0.1:5432/{{DB}}'
python3 backend/che168_scraper.py --config che168_scraper.yaml
```

**Что делает:** парсинг Che168; в конце может вызываться `postgres_catalog_sync` (если не отключено env `SKIP_POSTGRES_CATALOG_SYNC` / `SKIP_FRONTEND_EXPORT`).  
**Когда:** полный или догрузочный прогон Китая.

⚠️ Не подставляйте буквально `USER:PASS` из примеров — только реальные учётные данные.

---

### Che168: ежедневное обновление (один цикл)

```bash
cd /opt/rideauto
python3 backend/che168_daily_update.py --once --config che168_scraper.yaml
```

**Что делает:** инкрементальный цикл (discover, sold, `--only-pending` и т.д. по конфигу).  
**Когда:** cron/systemd или ручная догрузка.

---

## 🧹 Очистка кэша

### Redis: сброс кэша API через endpoint ✨

Только если задан `WRA_CACHE_INVALIDATE_SECRET` (в Docker: `WRA_CACHE_INVALIDATE_SECRET` в `.env` / compose).

```bash
curl -sS -X POST "http://127.0.0.1:8080/api/internal/cache/invalidate?scope=all" \
  -H "X-WRA-Admin-Key: {{ВСТАВЬТЕ_СЕКРЕТ_ИЗ_.ENV}}"
```

**Что делает:** очищает сегменты Redis-кэша (`all` | `search` | `facets` | `car`).  
**Когда:** данные в БД обновились, а выдача API «старая».

**Области:** `scope=search`, `scope=facets`, `scope=car` — точечно.

---

### Redis: flush вручную (⚠️ очень грубо)

```bash
cd /opt/rideauto
docker compose exec redis redis-cli FLUSHDB
```

**Что делает:** очищает текущую БД Redis (ключи этого инстанса).  
**Когда:** только если уверены, что в Redis нет ничего кроме кэша приложения.

⚠️ Удалит **все** ключи в выбранной DB Redis; на общем инстансе не использовать.

---

### Кэш картинок API (диск)

Каталог задаётся `WRA_IMAGE_CACHE_DIR` (в контейнере часто `/app/var/image_cache`).

```bash
# Пример: очистить volume/каталог только после остановки api или осознанно
docker compose exec api sh -c 'rm -rf /app/var/image_cache/*'
```

**Что делает:** сбрасывает WebP-кэш прокси `/api/images/...`.  
**Когда:** битые/устаревшие превью после смены логики прокси.

⚠️ Первые запросы к картинкам снова пойдут в CDN.

---

### Браузер

- Жёсткое обновление: `Ctrl+Shift+R` (Windows)  
- Или DevTools → Network → Disable cache → перезагрузка  

**Когда:** подозрение на старый JS/CSS (реже при Docker-деплое, чаще при CDN).

---

## 🔍 Диагностика и логи

### Systemd: логи API (если API на uvicorn через systemd, не Docker)

```bash
journalctl -u rideauto-api.service -f --no-pager
```

**Что делает:** поток логов юнита.  
**Когда:** на сервере поднят `rideauto-api.service` из `deploy/systemd/rideauto-api.service`.

---

### Docker: health API

```bash
curl -sS http://127.0.0.1:8080/api/health
```

**Что делает:** проверка живости FastAPI.  
**Когда:** «API не отвечает» — сначала с сервера localhost.

---

### Postgres: сколько машин Che168 в каталоге

```bash
docker compose exec postgres psql -U wra -d wra -c \
  "SELECT COUNT(*) FROM cars WHERE lower(trim(source)) = 'che168';"
```

**Что делает:** счётчик строк.  
**Когда:** проверка после скрейпера.

---

### Meilisearch: здоровье

```bash
curl -sS http://127.0.0.1:7700/health
```

**Что делает:** Meili жив.  
**Когда:** поиск пустой/ошибки — убедиться, что процесс отвечает.

---

## 🚀 Скрипты деплоя

Все пути относительно `/opt/rideauto`:

| Скрипт | Назначение (кратко) |
|--------|---------------------|
| `deploy/scripts/run_meilisearch_sync_host.sh` | Postgres → Meilisearch |
| `deploy/scripts/run_postgres_catalog_sync_host.sh` | Обогащение каталога в Postgres |
| `deploy/scripts/run_full_deploy_pipeline.sh` | Полный пайплайн (смотрите содержимое) |
| `deploy/scripts/backup_postgres_compose.sh` | Бэкап БД |
| `deploy/scripts/diagnose_nightly_updates.sh` | Диагностика ночных обновлений |
| `deploy/scripts/rideauto_git_pull.sh` | Обёртка git pull (если используете) |

Перед запуском читайте комментарии в начале каждого `.sh`.

---

## ❌ Частые ошибки

### `password authentication failed for user "USER"`

Вы в `DATABASE_URL` оставили плейсхолдер `USER`, а не реального пользователя Postgres.

**Решение:** возьмите DSN из `/etc/default/rideauto`, `.env` или того же источника, что работает для скрейпера.

---

### После `git push server` на сайте ничего не меняется

Пуш обновил **bare-репозиторий**, но не сам `/opt/rideauto`.

**Решение:** на сервере выполнить `git pull` / hook / ваш скрипт деплоя → затем `docker compose build` / `up -d` для затронутых сервисов.

---

### Поиск показывает старые данные, а в Postgres уже новое

**Решение:** ✨ `run_meilisearch_sync_host.sh`; при кэше API — `POST /api/internal/cache/invalidate`.

---

### Новые машины не в каталоге на сайте

1. Проверить count в `cars`.  
2. Meilisearch синк.  
3. Сброс Redis-кэша API.  
4. Проверить, что фронт бьёт в тот же API/индекс, что вы обновляете.

---

### `/api/car/...` 500, в логах `TimeoutError` (asyncpg)

Часто тяжёлый SQL по большой таблице `cars`. В актуальном коде поиск карточки разбит на быстрый путь по `car_id` и медленный по JSON — обновите API.

**Решение:** `git pull`, пересборка `api`, мониторинг `docker compose logs -f api`.

---

### API не отвечает

1. `docker compose ps`  
2. `curl http://127.0.0.1:8080/api/health`  
3. `docker compose logs api --tail=200`  
4. Если systemd: `systemctl status rideauto-api.service`

---

### Хочу «сбросить всё» и чистую базу ⚠️

1. Сделайте **бэкап**: `deploy/scripts/backup_postgres_compose.sh` или `pg_dump`.  
2. Осознайте последствия для Meili, Redis, пользователей.  
3. Типично: остановить сервисы → удалить volume Postgres **или** пересоздать БД → применить миграции/schema → полный импорт → полный синк Meili.

⚠️ **Не** выполняйте по инструкции из чата без своего runbook и бэкапа.

---

## 🔧 Полезные однострочники

### Последние 100 строк логов API

```bash
cd /opt/rideauto && docker compose logs api --tail=100
```

---

### Размер таблицы `cars`

```bash
docker compose exec postgres psql -U wra -d wra -c \
  "SELECT pg_size_pretty(pg_total_relation_size('cars'));"
```

---

### Список systemd-таймеров RideAuto (если установлены)

```bash
systemctl list-timers --all | grep -i rideauto
```

---

## ⚡ Быстрые комбо

### Обновить код на сервере и перезапустить API + web (Docker)

```bash
cd /opt/rideauto && git pull && docker compose build api web && docker compose up -d api web
```

**Когда:** типичный деплой после пуша в тот же репозиторий.

---

### «Данные в БД есть, поиск отстаёт»

```bash
sudo bash /opt/rideauto/deploy/scripts/run_meilisearch_sync_host.sh && \
curl -sS -X POST "http://127.0.0.1:8080/api/internal/cache/invalidate?scope=all" \
  -H "X-WRA-Admin-Key: {{ВСТАВЬТЕ_СЕКРЕТ_ИЗ_.ENV}}"
```

---

### Деплой + сразу смотреть логи

```bash
cd /opt/rideauto && git pull && docker compose up -d --build api web && docker compose logs -f api web
```

---

## Как добавить свою команду в этот файл

1. Выберите раздел (или создайте подраздел с эмодзи).  
2. Вставьте блок кода с командой **полностью**, как для копирования.  
3. Три строки текста: **что делает** / **когда использовать** / **⚠️ предупреждение** (если есть).  
4. Секреты только как `{{ПЛЕЙСХОЛДЕР}}`.  
5. Если команда специфична для вашего сервера (порты, пользователь БД) — добавьте пометку «у нас: …».  
6. В конце списка оглавления добавьте якорь на новый подраздел.

---

*Версия файла: согласована с репозиторием RideAuto (Compose-сервисы `api`, `web`, `postgres`, `redis`, `meilisearch`). При смене инфраструктуры обновите разделы вручную.*
