# Monitoring Quickstart (Slack)

Быстрый запуск мониторинга на хосте `/opt/rideauto`:

- Prometheus (scrape `127.0.0.1:8080/metrics`)
- Alertmanager (уведомления в Slack Incoming Webhook)

## 1) Подготовка

```bash
cd /opt/rideauto
git pull
```

Проверьте, что API отдаёт метрики:

```bash
curl -sS http://127.0.0.1:8080/metrics | head -30
```

## 2) Секрет Slack webhook

```bash
cd /opt/rideauto/deploy/monitoring/secrets
cp slack_webhook.example slack_webhook
nano slack_webhook
chmod 644 slack_webhook
```

`chmod 644` нужен, т.к. контейнеры `prom/*` обычно работают не от root.

## 3) Alertmanager (localhost only)

```bash
docker rm -f alertmanager 2>/dev/null || true
docker run -d --name alertmanager --restart unless-stopped \
  --network host \
  -v /opt/rideauto/deploy/monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro \
  -v /opt/rideauto/deploy/monitoring/alertmanager_templates:/etc/alertmanager/templates:ro \
  -v /opt/rideauto/deploy/monitoring/secrets/slack_webhook:/etc/alertmanager/secrets/slack_webhook:ro \
  prom/alertmanager:latest \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --web.listen-address=127.0.0.1:9093
```

UI: `http://127.0.0.1:9093`

## 4) Prometheus (localhost only)

```bash
docker rm -f prometheus 2>/dev/null || true
docker run -d --name prometheus --restart unless-stopped \
  --network host \
  -v /opt/rideauto/deploy/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro \
  -v /opt/rideauto/deploy/monitoring/alert_rules.yml:/etc/prometheus/alert_rules.yml:ro \
  prom/prometheus:latest \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.listen-address=127.0.0.1:9090
```

UI: `http://127.0.0.1:9090`

## 5) Проверка

1. Prometheus -> Status -> Targets: `rideauto-api` должен быть `UP`.
2. Prometheus -> Alerts: должны быть загружены правила.
3. Тест алерта: временно остановить `api` на 2-3 минуты или снизить порог в `alert_rules.yml`.
4. Проверить сообщение в Slack + resolved после восстановления.

## 6) Полезные команды

```bash
docker logs --tail=100 prometheus
docker logs --tail=100 alertmanager
curl -sG --data-urlencode 'query=up{job="rideauto-api"}' http://127.0.0.1:9090/api/v1/query
```

## 7) Che168-алерты

Для Che168 scraper используйте правила из:

- `deploy/prometheus/alert_rules_rideauto.yml`

и triage-процедуру из:

- `deploy/docs/RUNBOOK_OPERATIONS.md`
