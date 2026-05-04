# Мониторинг, нагрузка через nginx, операционка

Связано с **`docs/SLO.md`**. Цель: снимать SLI с **`GET /metrics`**, гонять **`load_profile.py`** по публичному URL и не светить метрики в интернет без защиты.

## Порядок на сервере (делай по шагам)

### Шаг 1 — убедиться, что API отдаёт метрики

```bash
curl -sS http://127.0.0.1:8080/metrics | head -30
```

Должны быть строки с префиксом **`wra_`**. Если пусто или 404 — проверь **`WRA_METRICS_ENABLED=true`** и контейнер **`api`**.

### Шаг 2 — подтянуть конфиг из репозитория

```bash
cd /opt/rideauto
git pull
```

Готовый конфиг: **`deploy/monitoring/prometheus.yml`** (scrapes `127.0.0.1:8080/metrics`).

### Шаг 3 — запустить Prometheus (Docker, только localhost UI)

Один контейнер с **host network** — так Prometheus видит тот же `127.0.0.1:8080`, что и API на хосте.

```bash
docker rm -f prometheus 2>/dev/null || true
docker run -d --name prometheus --restart unless-stopped \
  --network host \
  -v /opt/rideauto/deploy/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  prom/prometheus:latest \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.listen-address=127.0.0.1:9090
```

Интерфейс: **`http://127.0.0.1:9090`** (с сервера или через SSH tunnel). **Не** открывай 9090 в интернет без auth.

### Шаг 4 — проверить, что цель UP

В UI: **Status → Targets** — job **`rideauto-api`** должен быть **UP**.

### Шаг 5 — пробный запрос в Graph

Примеры PromQL:

```promql
rate(wra_http_requests_total{status_class="5xx"}[5m])
```

```promql
histogram_quantile(0.95, sum(rate(wra_http_request_duration_seconds_bucket[5m])) by (le, path_group))
```

Проверка из shell (есть ли серии):

```bash
curl -sG --data-urlencode 'query=up{job="rideauto-api"}' http://127.0.0.1:9090/api/v1/query | head -c 400
echo
```

### Шаг 6 — правила алертов + Alertmanager (опционально, но логично сразу после Prometheus)

В репозитории:

- **`deploy/monitoring/alert_rules.yml`** — алерты **5xx > 1%** (5m) и **target down**
- **`deploy/monitoring/alertmanager.yml`** — маршрут в **Telegram** (токен и chat id — только в файлах на сервере)

Обнови код:

```bash
cd /opt/rideauto && git pull
```

#### Telegram для Alertmanager

1. В Telegram: **@BotFather** → `/newbot` → сохрани **токен** бота.
2. Напиши боту любое сообщение (или добавь бота в группу и отправь сообщение в группу).
3. Узнай **chat_id**:
   ```bash
   curl -sS "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool
   ```
   В ответе смотри `message.chat.id` (для групп часто отрицательное число, например `-100…`).
4. На сервере создай секреты (одна строка в файле, без лишних пробелов и переводов строки после числа по возможности):
   ```bash
   cd /opt/rideauto/deploy/monitoring/secrets
   sudo cp bot_token.example bot_token
   sudo cp chat_id.example chat_id
   sudo nano bot_token chat_id   # подставь реальные значения
   sudo chmod 644 bot_token chat_id
   ```

   Образ **`prom/alertmanager`** работает **не от root**; при **`chmod 600`** и владельце **root** смонтированные файлы дают **`permission denied`** внутри контейнера. Поэтому на секретах нужно **`644`** (чтение для «остальных») либо **`chown`** под UID пользователя из `docker exec alertmanager id`.

**Сначала Alertmanager** (слушает только localhost), затем Prometheus:

```bash
docker rm -f alertmanager 2>/dev/null || true
docker run -d --name alertmanager --restart unless-stopped \
  --network host \
  -v /opt/rideauto/deploy/monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro \
  -v /opt/rideauto/deploy/monitoring/alertmanager_templates:/etc/alertmanager/templates:ro \
  -v /opt/rideauto/deploy/monitoring/secrets/bot_token:/etc/alertmanager/secrets/bot_token:ro \
  -v /opt/rideauto/deploy/monitoring/secrets/chat_id:/etc/alertmanager/secrets/chat_id:ro \
  prom/alertmanager:latest \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --web.listen-address=127.0.0.1:9093

docker rm -f prometheus
docker run -d --name prometheus --restart unless-stopped \
  --network host \
  -v /opt/rideauto/deploy/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  -v /opt/rideauto/deploy/monitoring/alert_rules.yml:/etc/prometheus/alert_rules.yml:ro \
  prom/prometheus:latest \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.listen-address=127.0.0.1:9090
```

Проверка: **Prometheus** → **Alerts** (правила загружены); **Alertmanager** `http://127.0.0.1:9093` — вкладка **Alerts** после срабатывания.

**Проверка Telegram:** временно останови **`api`** на пару минут или ослабь порог в **`alert_rules.yml`** — в чат должно прийти уведомление; после восстановления — сообщение о **resolved** (если включено `send_resolved`). После смены **`bot_token`** / **`chat_id`** пересоздай контейнер **`alertmanager`** с теми же volume.

### Дальше (следующие этапы)

1. При необходимости — второй receiver (email / Slack) через `route` `continue` и отдельные `receiver`.
2. **Копия бэкапов** с сервера (S3 / второй хост).
3. **Тестовое восстановление** дампа на отдельной ВМ.

---

## 1) Эндпоинт Prometheus

- **`GET /metrics`** (включается **`WRA_METRICS_ENABLED=true`**, по умолчанию так).
- Имена метрик (prefix **`wra_`**):
  - **`wra_http_request_duration_seconds`** — histogram, labels `method`, `path_group`
  - **`wra_http_requests_total`** — counter, labels `method`, `path_group`, `status_class` (`2xx`, `4xx`, `5xx`, …)
  - **`wra_cache_lookups_total`** — counter, `segment`, `result` (`hit` / `miss`)

`path_group` нормализуется (например `/api/car/{id}`), чтобы не раздувать кардинальность.

## 2) Как скрапить безопасно

**Рекомендуется:** Prometheus (или агент) на **том же хосте**, что и Docker, бьёт в **loopback**:

```yaml
# fragment: prometheus.yml scrape_configs
  - job_name: rideauto-api
    metrics_path: /metrics
    static_configs:
      - targets: ["127.0.0.1:8080"]
```

Тогда **не нужно** вывешивать `/metrics` на `https://rideauto.ru`. Если метрики нужны только с другой машины — используйте VPN / SSH tunnel / отдельный internal listener, либо **`deploy/nginx/location-metrics-proxy.snippet.conf`** с ограничением по IP.

## 3) Алерты (идеи под PromQL)

Точные выражения зависят от версии Prometheus и ваших recording rules. Ориентиры из **`docs/SLO.md`**:

- **Доля 5xx** за 5m > 1%: по `wra_http_requests_total` с label `status_class="5xx"`.
- **p95 latency** `/api/search` и `/api/car/{id}`: из `wra_http_request_duration_seconds` + `histogram_quantile(0.95, …)` с фильтром по `path_group`.

Сделайте **тестовый firing**: временно снизьте порог или используйте `curl` к тестовому rule в Alertmanager.

## 4) Нагрузка «как пользователь» (через nginx / TLS)

Из корня репозитория на сервере (или с машины, которой разрешён доступ к API по HTTPS):

```bash
python3 deploy/scripts/load_profile.py \
  --base-url https://rideauto.ru \
  --car-id "che168-EXAMPLE"
```

При самоподписанном сертификате или корпоративном CA:

```bash
python3 deploy/scripts/load_profile.py \
  --base-url https://rideauto.ru \
  --car-id "che168-EXAMPLE" \
  --insecure
```

Сравнивайте p95/p99 с baseline в **`docs/SLO.md`**; рост допустим из-за TLS и кэша nginx.

## 5) Бэкап PostgreSQL (Compose)

```bash
cd /opt/rideauto
chmod +x deploy/scripts/backup_postgres_compose.sh
./deploy/scripts/backup_postgres_compose.sh
```

По умолчанию каталог **`./backups/`** (в `.gitignore`). Логи крона удобно писать в `/var/log/rideauto-backup.log`.

**Cron (ежедневный бэкап + хранить 7 дней):**

```cron
15 3 * * * cd /opt/rideauto && ./deploy/scripts/backup_postgres_compose.sh >> /var/log/rideauto-backup.log 2>&1
20 3 * * * find /opt/rideauto/backups -maxdepth 1 -type f -name 'wra_*.dump' -mtime +7 -delete
```

`-mtime +7` удаляет дампы **старше 7 суток**. Путь `/opt/rideauto` при необходимости замените.

## 6) Секреты и пароли

- Не коммить **`.env`**. Ключи, попавшие в чат/логи, **ротировать**.
- В проде сменить дефолтные **`POSTGRES_PASSWORD`**, **`MEILI_MASTER_KEY`**, при необходимости Redis; синхронно обновить **`WRA_PG_DSN`** и перезапустить **`api`**.

## 7) Многопроцессный uvicorn

Если когда-нибудь включите **несколько воркеров** и **`PROMETHEUS_MULTIPROC_DIR`**, читайте комментарий в **`backend/fastapi_app/metrics/prometheus.py`** (MultiProcessCollector).
