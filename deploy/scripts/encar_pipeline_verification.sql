-- Проверка пайплайна Encar по данным в Postgres.
-- Запускайте дважды: после encar_scraper и после postgres_catalog_sync (смотрите по полям ниже).

\set ON_ERROR_STOP on

-- ---------------------------------------------------------------------------
-- Сводка: одна строка — удобно сравнивать до/после catalog_sync по одному и тому же запросу.
-- ---------------------------------------------------------------------------
SELECT
  'encar_inventory' AS checkpoint,
  COUNT(*) AS cars,
  ROUND(100.0 * COUNT(*) FILTER (WHERE COALESCE(mark, '') <> '') / NULLIF(COUNT(*), 0), 1) AS pct_mark,
  ROUND(100.0 * COUNT(*) FILTER (WHERE COALESCE(model, '') <> '') / NULLIF(COUNT(*), 0), 1) AS pct_model,
  COUNT(*) FILTER (WHERE year IS NOT NULL AND year > 0) AS has_year_col,
  COUNT(*) FILTER (WHERE data ? 'price_won') AS json_key_price_won,
  COUNT(*) FILTER (WHERE data ? 'price') AS json_key_price_manwon,
  COUNT(*) FILTER (
    WHERE NULLIF(trim(COALESCE(data ->> 'price_won', '')), '') IS NOT NULL
         AND trim(data ->> 'price_won') NOT IN ('0')
  ) AS json_price_won_nonempty,
  COUNT(*) FILTER (
    WHERE NULLIF(trim(COALESCE(data ->> 'price', '')), '') IS NOT NULL
         AND trim(COALESCE(data ->> 'price', '')) NOT IN ('0', 'none', 'null')
  ) AS json_price_field_nonempty,
  COUNT(*) FILTER (WHERE raw IS NOT NULL) AS rows_with_raw,
  COUNT(*) FILTER (WHERE COALESCE(price_rub, 0) > 0) AS col_price_rub_gt_0,
  COUNT(*) FILTER (
    WHERE jsonb_typeof(data -> 'pricing_clean') = 'object'
  ) AS json_pricing_clean_object,
  COUNT(*) FILTER (WHERE data ? 'pricing_tier') AS json_has_pricing_tier,
  COUNT(*) FILTER (WHERE jsonb_typeof(data -> 'my_price') IN ('number', 'string'))
    AS json_has_my_price_scalar,
  COUNT(*) FILTER (WHERE (data -> 'price_on_request') = 'true'::jsonb) AS price_on_request
FROM cars
WHERE source = 'encar';

-- Случайные примеры строк (структура data после парсера; pricing_clean после catalog_sync).
SELECT
  car_id,
  substring(COALESCE(mark, ''), 1, 26) AS mark,
  substring(COALESCE(model, ''), 1, 26) AS model,
  year,
  data ->> 'price_won' AS price_won_raw,
  data ->> 'price' AS price_manwon_parser,
  data ->> 'pricing_tier' AS pricing_tier,
  COALESCE(price_rub, 0) > 0 AS col_price_positive,
  (jsonb_typeof(data -> 'pricing_clean') = 'object') AS has_pricing_clean_object
FROM cars
WHERE source = 'encar'
  AND data IS NOT NULL
ORDER BY random()
LIMIT 12;
