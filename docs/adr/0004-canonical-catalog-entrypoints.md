# ADR 0004: Canonical catalog entrypoints (one happy path)

- **Статус:** принято  
- **Дата:** 2026-10-06  

## Контекст

Два способа обновить каталог (отдельные PG/Meili скрипты vs `run_catalog_pipeline_host.sh`) и два Meili-пути (full sync vs outbox) размывали «что канон».

## Решение

1. **Канон ночного/полного обновления индекса:** только [`deploy/scripts/run_catalog_pipeline_host.sh`](../../deploy/scripts/run_catalog_pipeline_host.sh) (и timer `rideauto-catalog-pipeline`).
2. **`run_full_deploy_pipeline.sh`** вызывает catalog pipeline, а не отдельные PG+Meili шаги.
3. **Meili outbox** — только инкремент между полными прогонами (near-realtime sold/price), не замена pipeline. Consistency gate: `catalog_meili_consistency.py`.
4. Legacy `run_system.py` / `parser_full.py` — только `WRA_ENABLE_LEGACY_ORCHESTRATION=1`.

## Последствия

- Метрики `wra_catalog_pipeline` / lag — единый сигнал свежести.
- Документация и README ссылаются на один happy path.
