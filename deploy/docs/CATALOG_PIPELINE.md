# Catalog Pipeline Platform

Единый оркестратор: **Postgres prices → Meilisearch** без опустошения live-индекса.

## Запуск

```bash
# Полный пайплайн (хост /opt/rideauto)
sudo -u rideauto bash /opt/rideauto/deploy/scripts/run_catalog_pipeline_host.sh

# Systemd
sudo systemctl enable --now rideauto-catalog-pipeline.timer
sudo systemctl start rideauto-catalog-pipeline.service
```

Скрипты стадий: [`run_postgres_catalog_sync_host.sh`](../scripts/run_postgres_catalog_sync_host.sh), [`run_meilisearch_sync_host.sh`](../scripts/run_meilisearch_sync_host.sh), оркестратор [`run_catalog_pipeline_host.sh`](../scripts/run_catalog_pipeline_host.sh).

## Blue/green (обязательно при recreate)

В `/etc/default/rideauto`:

```bash
WRA_MEILISEARCH_INDEX=cars_build
WRA_MEILI_LIVE_INDEX=cars
WRA_MEILI_SWAP_INTO_LIVE=1
WRA_MEILI_PREFLIGHT_GATE=true
```

`sync_meilisearch.py` **отказывает** `--recreate-index` на live UID без `--swap-into-live` (fail-closed).

## Метрики (node_exporter textfile)

| Metric | Meaning |
|--------|---------|
| `wra_job_last_*{job="wra_catalog_pipeline"}` | Оркестратор |
| `wra_job_last_*{job="wra_postgres_catalog_sync"}` | Стадия PG |
| `wra_job_last_*{job="wra_meilisearch_sync"}` | Стадия Meili |
| `wra_catalog_pg_active_rows` | PG rows без dedupe link |
| `wra_catalog_meili_documents` | Live Meili docs |
| `wra_catalog_index_empty` | 1 если Meili пуст |
| `wra_catalog_meili_pg_ratio` | docs/rows |

Каталог lag: [`backend/scripts/catalog_pipeline_lag_metrics.py`](../../backend/scripts/catalog_pipeline_lag_metrics.py).

## Прод-Done gate

1. Timer активен; last success < 26h.
2. `wra_catalog_meili_documents > 0`.
3. Preflight проходит или override задокументирован.
4. Алерт `RideautoCatalogIndexEmpty` не firing в норме.

См. также [`backend/docs/RELEASE_CHECKLIST_CATALOG.md`](../../backend/docs/RELEASE_CHECKLIST_CATALOG.md) §0.
