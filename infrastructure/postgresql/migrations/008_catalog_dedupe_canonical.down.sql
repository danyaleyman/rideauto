-- Откат 008_catalog_dedupe_canonical.sql (только для drill/CI; на проде — с осторожностью).
-- psql "$DATABASE_URL" -f infrastructure/postgresql/migrations/008_catalog_dedupe_canonical.down.sql

DROP INDEX IF EXISTS idx_cars_meili_source_rows;
DROP INDEX IF EXISTS idx_cars_dedupe_canonical_target;
ALTER TABLE cars DROP COLUMN IF EXISTS dedupe_canonical_car_id;
