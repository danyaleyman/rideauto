-- Очередь пересчёта цены/tier после частичных апдейтов data (см. backend/docs/PRICING_PIPELINE.md).
-- psql "$DATABASE_URL" -f infrastructure/postgresql/migrations/007_pricing_recompute_queue.sql

ALTER TABLE cars ADD COLUMN IF NOT EXISTS needs_pricing_recompute BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN cars.needs_pricing_recompute IS
    'true: карточку нужно прогнать через postgres_catalog_sync с ценами; сбрасывается после успешного upsert с расчётом цен.';

CREATE INDEX IF NOT EXISTS idx_cars_needs_pricing_recompute_encar
    ON cars (updated_at DESC)
    WHERE needs_pricing_recompute IS TRUE
      AND (source IS NULL OR source = '' OR lower(source) = 'encar')
      AND (car_id IS NULL OR car_id NOT LIKE 'che168-%');
