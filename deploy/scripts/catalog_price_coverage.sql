-- Аудит покрытия price_rub в Postgres (соответствует логике колонки cars.price_rub).
-- Префлайт Meili считает только source = 'encar' (см. backend/scripts/meili_sync_preflight.py).

\x off
\set ON_ERROR_STOP on

-- 1) По маркету (колонка cars.source): сколько строк и сколько с price_rub > 0
SELECT
  COALESCE(NULLIF(trim(source), ''), '(empty)') AS source,
  COUNT(*)                                           AS listings,
  COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0) AS price_rub_gt_0,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0)
    / NULLIF(COUNT(*), 0),
    2
  ) AS pct_with_price_rub
FROM cars
GROUP BY 1
ORDER BY listings DESC;

-- 2) Только Encar — как префлайт индекса (без фильтра по марке/модели в WHERE)
SELECT
  COUNT(*)                                           AS encar_total,
  COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0) AS encar_price_rub_gt_0,
  COUNT(*) FILTER (WHERE COALESCE(mark, '') <> '')  AS encar_has_mark,
  COUNT(*) FILTER (WHERE COALESCE(model, '') <> '')  AS encar_has_model,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0)
    / NULLIF(COUNT(*), 0),
    2
  ) AS pct_price_encar,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE COALESCE(mark, '') <> '')
    / NULLIF(COUNT(*), 0),
    2
  ) AS pct_brand_encar,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE COALESCE(model, '') <> '')
    / NULLIF(COUNT(*), 0),
    2
  ) AS pct_model_encar
FROM cars
WHERE source = 'encar';

-- 3) Encar: флаги из JSON vs колонка (почему нет цены в выдаче поиска).
-- Булевы в JSONB — безопасно через jsonb (не ::boolean на text).
SELECT
  COUNT(*) AS encar_total,
  COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0) AS col_price_gt_0,
  COUNT(*) FILTER (WHERE (data -> 'price_on_request') = 'true'::jsonb) AS data_price_on_request,
  COUNT(*) FILTER (WHERE (data -> 'encar_listing_reserved') = 'true'::jsonb) AS data_encar_reserved_placeholder,
  COUNT(*) FILTER (WHERE (data -> 'price_calc_failed') = 'true'::jsonb) AS data_price_calc_failed
FROM cars
WHERE source = 'encar';

-- 4) Che168 (если есть в БД): то же покрытие
SELECT
  COUNT(*)                                           AS che168_total,
  COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0) AS price_rub_gt_0,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0)
    / NULLIF(COUNT(*), 0),
    2
  ) AS pct_with_price_rub
FROM cars
WHERE source = 'che168';
