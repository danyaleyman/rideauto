-- Флаги дневного чекера «продано на Encar» (скрипт encar_listing_live_checker.py).
-- Применить на существующей БД: psql "$DATABASE_URL" -f infrastructure/postgresql/migrations/002_encar_listing_flags.sql

ALTER TABLE cars ADD COLUMN IF NOT EXISTS encar_listing_sold BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE cars ADD COLUMN IF NOT EXISTS encar_listing_checked_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_cars_encar_listing_checker
    ON cars (encar_listing_checked_at NULLS FIRST)
    WHERE (source IS NULL OR source = 'encar')
      AND (car_id IS NULL OR car_id NOT LIKE 'che168-%');
